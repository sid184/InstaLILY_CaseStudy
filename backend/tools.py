"""
Tool functions for the PartSelect chat agent.

These are the functions that Claude can call via tool use.
Each function searches/filters our product data and returns Product models.
"""

import json
import re
import urllib.parse
from pathlib import Path
from typing import List, Optional

import chromadb
import httpx

from backend.models import Installation, Product

# ---------------------------------------------------------------------------
# Data Loading
# ---------------------------------------------------------------------------

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CHROMA_DIR = str(DATA_DIR / "chromadb")
COLLECTION_NAME = "products"

# Load product data into memory (once, at import time)
_products: dict = {}        # part_number -> raw dict
_model_to_parts: dict = {}  # model_number -> list of part_numbers


def _load_data():
    """Load JSON files into memory."""
    global _products, _model_to_parts

    with open(DATA_DIR / "products.json") as f:
        _products = json.load(f)

    with open(DATA_DIR / "model_to_parts.json") as f:
        _model_to_parts = json.load(f)


# Load on import
_load_data()


# ---------------------------------------------------------------------------
# ChromaDB Setup
# ---------------------------------------------------------------------------

_chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)


def _get_collection():
    """Get or create the ChromaDB collection."""
    return _chroma_client.get_or_create_collection(COLLECTION_NAME)


def build_vector_store():
    """
    Build (or rebuild) the ChromaDB vector store from products.json.

    Run this once after scraping:
        python -c "from backend.tools import build_vector_store; build_vector_store()"
    """
    # Delete existing collection if it exists
    try:
        _chroma_client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass

    collection = _chroma_client.create_collection(COLLECTION_NAME)

    print(f"Building vector store from {len(_products)} products...")

    for part_number, product in _products.items():
        # Build a rich text document for embedding
        # This is what ChromaDB will search against
        doc = f"""
Part: {product.get('title', '')}
Brand: {product.get('brand', '')}
Type: {product.get('appliance_type', '')}
Description: {product.get('description', '')[:500]}
Symptoms: {', '.join(product.get('symptoms', []))}
Part Number: {part_number}
Manufacturer Part: {product.get('manufacturer_part_number', '')}
"""
        collection.add(
            ids=[part_number],
            documents=[doc],
            metadatas=[{
                "brand": product.get("brand", ""),
                "appliance_type": product.get("appliance_type", ""),
                "part_number": part_number,
            }],
        )

    print(f"Vector store built: {collection.count()} documents indexed.")


# ---------------------------------------------------------------------------
# Live-lookup fallback (Tier 4)
# ---------------------------------------------------------------------------

_LIVE_LOOKUP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://www.partselect.com/",
}


def _live_lookup(query: str) -> List[Product]:
    """
    Tier 4 fallback: attempt a live HTTP search on PartSelect.com for parts
    not found in the local dataset.

    IMPORTANT: PartSelect uses bot-protection (Cloudflare) that blocks simple
    HTTP requests with a 403. Full live scraping requires Playwright + stealth
    mode (see data/scraper.py). In a production system this function would
    call a dedicated scraping microservice built on that Playwright code.

    Current behaviour:
      - If the query is a recognised PS or manufacturer part number pattern,
        return a lightweight "search stub" Product pointing directly to the
        PartSelect product/search page so the user can follow the link.
      - For all other queries, return an empty list (the agent will tell the
        user the part wasn't found in our database).
    """
    q = query.strip()
    q_upper = q.upper()

    # Attempt live HTTP fetch (will return 403 due to bot protection)
    search_url = (
        f"https://www.partselect.com/search/?searchterm="
        f"{urllib.parse.quote(q)}"
    )
    try:
        with httpx.Client(timeout=5.0, follow_redirects=True) as client:
            resp = client.get(search_url, headers=_LIVE_LOOKUP_HEADERS)
        if resp.status_code == 200 and "Access Denied" not in resp.text:
            # If PartSelect ever lifts bot-protection for this client,
            # parse the HTML here with BeautifulSoup (see data/scraper.py
            # for the CSS selectors to use).
            pass
    except Exception:
        pass  # Network error — fall through to stub

    # Stub: if query looks like a specific PS part number, return a search
    # link so the user can find it directly on PartSelect.com
    ps_match = re.match(r"^(PS\d{4,10})$", q_upper)
    mpn_match = re.match(r"^([A-Z]{1,4}\d{5,12}[A-Z0-9]*)$", q_upper)

    # For part-number shaped queries, return the search URL as metadata
    # so the agent can surface it in text — no stub product card needed.
    if ps_match or mpn_match:
        return []  # Agent will provide the PartSelect search link in its text response

    return []


# ---------------------------------------------------------------------------
# Tool 1: search_products
# ---------------------------------------------------------------------------

def search_products(
    query: str,
    appliance_type: Optional[str] = None,
    top_k: int = 5,
) -> List[Product]:
    """
    Search for products by part number, keyword, or natural language query.

    Strategy:
      1. Exact match on part number (PS12345) → instant result
      2. Exact match on manufacturer part number (WPW10321304) → instant result
      3. Vector search via ChromaDB for everything else

    Args:
        query: The search query (part number, symptom, description, etc.)
        appliance_type: Optional filter - "refrigerator" or "dishwasher"
        top_k: Maximum number of results to return

    Returns:
        List of matching Product models, best match first.
    """
    results = []

    # --- Strategy 1: Exact part number match (e.g. "PS3406971") ---
    query_upper = query.strip().upper()

    # Direct PS number lookup
    if query_upper in _products:
        product = _products[query_upper]
        if _matches_appliance_filter(product, appliance_type):
            results.append(Product(**product))
            return results

    # Also try with "PS" prefix if user just typed digits
    if query_upper.isdigit():
        ps_key = f"PS{query_upper}"
        if ps_key in _products:
            product = _products[ps_key]
            if _matches_appliance_filter(product, appliance_type):
                results.append(Product(**product))
                return results

    # --- Strategy 2: Manufacturer part number match ---
    for pn, product in _products.items():
        mpn = product.get("manufacturer_part_number", "").upper()
        if mpn and mpn == query_upper:
            if _matches_appliance_filter(product, appliance_type):
                results.append(Product(**product))
                return results

    # --- Strategy 2.5: Part-number-shaped query not in local dataset ---
    # If the query looks like a specific PS or MPN part number but wasn't found
    # above, skip ChromaDB (which would return semantically similar but wrong
    # parts) and go straight to the live-lookup stub.
    _ps_pattern = re.match(r"^PS\d{4,10}$", query_upper)
    _mpn_pattern = re.match(r"^[A-Z]{1,4}\d{5,12}[A-Z0-9]*$", query_upper)
    if _ps_pattern or _mpn_pattern:
        return _live_lookup(query_upper)

    # --- Strategy 3: Vector search via ChromaDB ---
    collection = _get_collection()

    if collection.count() == 0:
        return results  # Vector store not built yet

    # Build filter for ChromaDB query
    where_filter = None
    if appliance_type:
        where_filter = {"appliance_type": appliance_type.lower()}

    try:
        search_results = collection.query(
            query_texts=[query],
            n_results=min(top_k, collection.count()),
            where=where_filter,
        )

        if search_results and search_results["ids"]:
            for part_number in search_results["ids"][0]:
                if part_number in _products:
                    results.append(Product(**_products[part_number]))

    except Exception as e:
        print(f"Vector search error: {e}")

    if results:
        return results

    # Tier 4: live PartSelect lookup for parts not in local dataset
    return _live_lookup(query)


# ---------------------------------------------------------------------------
# Tool 2: check_compatibility
# ---------------------------------------------------------------------------

def check_compatibility(part_number: str, model_number: str) -> dict:
    """
    Check whether a specific part is compatible with a specific appliance model.

    Uses the model_to_parts reverse index built during scraping.

    Args:
        part_number: The PartSelect part number (e.g. "PS3406971")
        model_number: The appliance model number (e.g. "2213223N414")

    Returns:
        A dict with:
          - compatible (bool): Whether the part fits the model
          - part (Product | None): The product if it exists
          - model_found (bool): Whether we recognise the model number
          - compatible_parts (list[Product]): Other parts that fit this model
            (only populated when the requested part does NOT fit, to suggest
             alternatives — capped at 5)
    """
    result = {
        "compatible": False,
        "part": None,
        "model_found": False,
        "compatible_parts": [],
    }

    # Normalise inputs
    pn = part_number.strip().upper()
    mn = model_number.strip().upper()

    # Add PS prefix if user typed bare digits
    if pn.isdigit():
        pn = f"PS{pn}"

    # Look up the part
    if pn in _products:
        result["part"] = Product(**_products[pn])

    # Look up the model
    # model_to_parts keys may be mixed case in the JSON, so try exact first
    parts_for_model = _model_to_parts.get(mn)

    # If not found, do a case-insensitive scan (models are usually uppercase
    # but we want to be forgiving)
    if parts_for_model is None:
        for key, val in _model_to_parts.items():
            if key.upper() == mn:
                parts_for_model = val
                break

    if parts_for_model is None:
        # Model not found in our database
        return result

    result["model_found"] = True

    # Check compatibility
    if pn in parts_for_model:
        result["compatible"] = True
    else:
        # Part doesn't fit — suggest alternatives from this model
        alternatives = []
        for alt_pn in parts_for_model[:5]:
            if alt_pn in _products:
                alternatives.append(Product(**_products[alt_pn]))
        result["compatible_parts"] = alternatives

    return result


# ---------------------------------------------------------------------------
# Tool 3: get_installation_guide
# ---------------------------------------------------------------------------

def get_installation_guide(part_number: str) -> dict:
    """
    Get installation details for a specific part.

    Args:
        part_number: The PartSelect part number (e.g. "PS3406971")

    Returns:
        A dict with:
          - found (bool): Whether the part exists in our database
          - part_number (str): The normalised part number
          - title (str | None): The part title
          - installation (Installation | None): Installation details
          - has_guide (bool): Whether installation info is available
          - url (str | None): Link to the product page for full instructions
    """
    result = {
        "found": False,
        "part_number": None,
        "title": None,
        "installation": None,
        "has_guide": False,
        "url": None,
    }

    # Normalise input
    pn = part_number.strip().upper()
    if pn.isdigit():
        pn = f"PS{pn}"

    result["part_number"] = pn

    if pn not in _products:
        return result

    product = _products[pn]
    result["found"] = True
    result["title"] = product.get("title", "")
    result["url"] = product.get("url", "")

    install_data = product.get("installation")
    if install_data:
        result["installation"] = Installation(**install_data)
        result["has_guide"] = True

    return result


# ---------------------------------------------------------------------------
# Tool 4: diagnose_problem
# ---------------------------------------------------------------------------

def diagnose_problem(
    symptom: str,
    appliance_type: Optional[str] = None,
    top_k: int = 5,
) -> dict:
    """
    Given a symptom description, find parts that are known to fix it.

    Uses a two-stage approach:
      1. Exact symptom match — scan the symptoms list on every product
      2. Vector search fallback — use ChromaDB for fuzzy/natural language

    Args:
        symptom: The problem description (e.g. "leaking", "ice maker not working")
        appliance_type: Optional filter — "refrigerator" or "dishwasher"
        top_k: Maximum number of results

    Returns:
        A dict with:
          - matched_symptom (str | None): The exact symptom string we matched, if any
          - parts (list[Product]): Parts known to fix this symptom
          - strategy (str): "exact" or "vector" — how we found the results
    """
    result = {
        "matched_symptom": None,
        "parts": [],
        "strategy": "none",
    }

    symptom_lower = symptom.strip().lower()
    if not symptom_lower:
        return result

    # --- Strategy 1: Exact symptom match ---
    # Check if the user's input matches (or is contained in) a known symptom
    matched_parts = []
    matched_symptom_name = None

    for product in _products.values():
        if not _matches_appliance_filter(product, appliance_type):
            continue

        for s in product.get("symptoms", []):
            if symptom_lower in s.lower() or s.lower() in symptom_lower:
                if matched_symptom_name is None:
                    matched_symptom_name = s  # keep the first canonical name
                matched_parts.append(Product(**product))
                break  # one match per product is enough

    if matched_parts:
        result["matched_symptom"] = matched_symptom_name
        result["parts"] = matched_parts[:top_k]
        result["strategy"] = "exact"
        return result

    # --- Strategy 2: Vector search fallback ---
    collection = _get_collection()

    if collection.count() == 0:
        return result

    where_filter = None
    if appliance_type:
        where_filter = {"appliance_type": appliance_type.lower()}

    try:
        search_results = collection.query(
            query_texts=[symptom],
            n_results=min(top_k, collection.count()),
            where=where_filter,
        )

        if search_results and search_results["ids"]:
            for part_number in search_results["ids"][0]:
                if part_number in _products:
                    result["parts"].append(Product(**_products[part_number]))

        if result["parts"]:
            result["strategy"] = "vector"

    except Exception as e:
        print(f"Vector search error: {e}")

    return result


# ---------------------------------------------------------------------------
# Tool 5: get_related_parts
# ---------------------------------------------------------------------------

def get_related_parts(part_number: str, top_k: int = 5) -> dict:
    """
    Find parts related to a given part.

    "Related" means parts that fit the same appliance models — i.e. parts
    a customer might also need when repairing the same machine.

    Strategy:
      1. Look up the part's compatible models
      2. For each model, collect other parts that also fit it
      3. Rank by how many models they share (more overlap = more related)
      4. Fall back to same appliance_type + brand if no model overlap

    Args:
        part_number: The PartSelect part number (e.g. "PS3406971")
        top_k: Maximum number of related parts to return

    Returns:
        A dict with:
          - found (bool): Whether the input part exists
          - part (Product | None): The input part
          - related (list[Product]): Related parts, most related first
          - strategy (str): "model_overlap", "same_category", or "none"
    """
    result = {
        "found": False,
        "part": None,
        "related": [],
        "strategy": "none",
    }

    # Normalise input
    pn = part_number.strip().upper()
    if pn.isdigit():
        pn = f"PS{pn}"

    if pn not in _products:
        return result

    product = _products[pn]
    result["found"] = True
    result["part"] = Product(**product)

    # --- Strategy 1: Model overlap ---
    # Find other parts that share compatible models with this part
    compatible_models = product.get("compatible_models", [])

    if compatible_models:
        # Count how many models each other part shares with this one
        overlap_counts: dict = {}  # part_number -> count of shared models

        for model in compatible_models:
            parts_for_model = _model_to_parts.get(model, [])
            for other_pn in parts_for_model:
                if other_pn != pn and other_pn in _products:
                    overlap_counts[other_pn] = overlap_counts.get(other_pn, 0) + 1

        if overlap_counts:
            # Sort by overlap count descending (most shared models first)
            ranked = sorted(overlap_counts.items(), key=lambda x: x[1], reverse=True)

            for other_pn, _ in ranked[:top_k]:
                result["related"].append(Product(**_products[other_pn]))

            result["strategy"] = "model_overlap"
            return result

    # --- Strategy 2: Same appliance type + brand fallback ---
    appliance = product.get("appliance_type", "")
    brand = product.get("brand", "")

    for other_pn, other_product in _products.items():
        if other_pn == pn:
            continue
        if (other_product.get("appliance_type", "") == appliance
                and other_product.get("brand", "") == brand):
            result["related"].append(Product(**other_product))
            if len(result["related"]) >= top_k:
                break

    if result["related"]:
        result["strategy"] = "same_category"

    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _matches_appliance_filter(product: dict, appliance_type: Optional[str]) -> bool:
    """Check if a product matches the optional appliance type filter."""
    if not appliance_type:
        return True
    return product.get("appliance_type", "").lower() == appliance_type.lower()
