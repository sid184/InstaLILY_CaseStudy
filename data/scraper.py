"""
PartSelect Product Scraper

Scrapes refrigerator and dishwasher parts from PartSelect.com.
Extracts product details, compatibility data, symptoms, and installation info.

Usage:
    python data/scraper.py

Output:
    data/scraped_parts.json   - Raw list of all scraped products
    data/products.json        - Products keyed by part number
    data/model_to_parts.json  - Model number → list of compatible part numbers
"""

import asyncio
import json
import os
import random
import re
from pathlib import Path
from collections import defaultdict

from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

BASE_URL = "https://www.partselect.com"
OUTPUT_DIR = Path("data")

CATEGORY_URLS = {
    "refrigerator": f"{BASE_URL}/Refrigerator-Parts.htm",
    "dishwasher": f"{BASE_URL}/Dishwasher-Parts.htm",
}

MAX_PARTS_PER_CATEGORY = 250  # 250 fridge + 250 dishwasher = ~500 total
SAVE_EVERY = 20  # Save progress to disk every N parts
MIN_DELAY = 2  # Min seconds between requests
MAX_DELAY = 4  # Max seconds between requests


# ---------------------------------------------------------------------------
# Browser Setup
# ---------------------------------------------------------------------------

async def create_browser(playwright):
    """Launch a browser that looks like a real user."""

    browser = await playwright.chromium.launch(
        headless=False,
        args=["--disable-blink-features=AutomationControlled"],
    )

    context = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1920, "height": 1080},
        locale="en-US",
    )

    page = await context.new_page()

    # Hide the webdriver flag so sites can't detect automation
    await page.add_init_script(
        'Object.defineProperty(navigator, "webdriver", {get: () => undefined});'
    )

    return browser, context, page


async def random_delay():
    """Wait a random amount of time between requests."""
    await asyncio.sleep(random.uniform(MIN_DELAY, MAX_DELAY))


# ---------------------------------------------------------------------------
# Step 1: Collect Product URLs from Category Pages
# ---------------------------------------------------------------------------

async def collect_product_urls(page, category_url, max_pages=5):
    """Visit a category page (and subsequent pages) and find all product links."""

    product_urls = []
    current_url = category_url

    for page_num in range(1, max_pages + 1):
        try:
            resp = await page.goto(current_url, wait_until="domcontentloaded", timeout=30000)
            if resp.status != 200:
                print(f"  WARNING: Got status {resp.status} for {current_url}")
                break

            await random_delay()
            soup = BeautifulSoup(await page.content(), "html.parser")

            # Find all links that look like product pages (contain /PS followed by digits)
            found_on_page = 0
            for link in soup.find_all("a", href=True):
                href = link["href"]
                if re.search(r'/PS\d{5,}.*\.htm', href):
                    clean = re.sub(r'\?.*$', '', href)
                    clean = re.sub(r'#.*$', '', clean)
                    full_url = clean if clean.startswith("http") else BASE_URL + clean
                    if full_url not in product_urls:
                        product_urls.append(full_url)
                        found_on_page += 1

            print(f"    Page {page_num}: found {found_on_page} new product URLs")

            # Find "Next" pagination link
            next_link = None
            for link in soup.find_all("a", href=True):
                text = link.get_text(strip=True).lower()
                href = link["href"]
                if text in ("next", "›", "»", "next page") or (
                    re.search(r'[?&]start=\d+', href) and "next" in text
                ):
                    next_link = href if href.startswith("http") else BASE_URL + href
                    break

            # Also check for numbered pagination — look for current page + 1
            if not next_link:
                active = soup.select_one(".pagination .active, .pager .current, [aria-current='page']")
                if active:
                    next_sibling = active.find_next_sibling("a")
                    if next_sibling and next_sibling.get("href"):
                        href = next_sibling["href"]
                        next_link = href if href.startswith("http") else BASE_URL + href

            if not next_link or found_on_page == 0:
                break  # No more pages

            current_url = next_link

        except Exception as e:
            print(f"  ERROR collecting URLs from {current_url}: {e}")
            break

    return product_urls


async def collect_brand_page_urls(page, category_url, category):
    """Find links to brand-specific pages (e.g., Whirlpool-Dishwasher-Parts.htm)."""

    brand_urls = []

    try:
        resp = await page.goto(category_url, wait_until="domcontentloaded", timeout=30000)
        if resp.status != 200:
            return []

        await random_delay()
        soup = BeautifulSoup(await page.content(), "html.parser")

        # Brand pages follow pattern: /BrandName-Refrigerator-Parts.htm
        appliance_name = "Refrigerator" if category == "refrigerator" else "Dishwasher"
        pattern = rf'/[A-Za-z]+-{appliance_name}-Parts\.htm'

        for link in soup.find_all("a", href=True):
            href = link["href"]
            if re.search(pattern, href):
                full_url = href if href.startswith("http") else BASE_URL + href
                if full_url not in brand_urls:
                    brand_urls.append(full_url)

    except Exception as e:
        print(f"  ERROR collecting brand pages: {e}")

    return brand_urls


# ---------------------------------------------------------------------------
# Step 2: Scrape Individual Product Pages
# ---------------------------------------------------------------------------

async def scrape_product_page(page, url):
    """Visit a single product page and extract all available data."""

    try:
        resp = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        if resp.status != 200:
            return None

        await random_delay()
        soup = BeautifulSoup(await page.content(), "html.parser")

        # --- Part number (from URL, always available) ---
        ps_match = re.search(r'PS(\d+)', url)
        if not ps_match:
            return None

        part_number = f"PS{ps_match.group(1)}"

        product = {
            "part_number": part_number,
            "url": url,
        }

        # --- Title (proven selector) ---
        try:
            title_el = soup.select_one("h1")
            if title_el:
                product["title"] = title_el.get_text(strip=True)
        except Exception:
            pass

        # --- Price ---
        try:
            # The price div has class "price" (plus other classes like "mt-sm-2")
            # and contains <span class="price__currency">$</span>32.91
            price_el = soup.find("span", class_="price__currency")
            if price_el and price_el.parent:
                price_text = price_el.parent.get_text(strip=True)
                price_match = re.search(r'\$([\d,.]+)', price_text)
                if price_match:
                    product["price"] = float(price_match.group(1).replace(",", ""))
        except Exception:
            pass

        # --- Description (proven selector) ---
        try:
            desc_el = soup.select_one(".pd__description")
            if desc_el:
                product["description"] = desc_el.get_text(strip=True)[:2000]
        except Exception:
            pass

        # --- Availability (proven selector) ---
        try:
            stock_el = soup.select_one(".pd__ships-today")
            product["in_stock"] = stock_el is not None
        except Exception:
            product["in_stock"] = False

        # --- Compatible models (proven selector) ---
        try:
            crossref = soup.select_one(".pd__crossref__list")
            if crossref:
                model_links = crossref.find_all("a")
                models = []
                for link in model_links:
                    model_text = link.get_text(strip=True)
                    if (model_text
                            and any(c.isdigit() for c in model_text)
                            and 6 <= len(model_text) <= 15):
                        models.append(model_text.upper())
                if models:
                    product["compatible_models"] = list(set(models))
        except Exception:
            pass

        # --- Manufacturer part number ---
        try:
            # Look for "Manufacturer Part Number" text on page
            for el in soup.find_all(string=re.compile(r'Manufacturer Part Number', re.I)):
                parent = el.parent
                if parent:
                    text = parent.get_text(strip=True)
                    mpn_match = re.search(r'Manufacturer Part Number\s*[:\s]*(\S+)', text)
                    if mpn_match:
                        product["manufacturer_part_number"] = mpn_match.group(1)
                        break
        except Exception:
            pass

        # --- Brand (extract from URL, most reliable) ---
        try:
            known_brands = [
                "Whirlpool", "Frigidaire", "Samsung", "LG",
                "KitchenAid", "Maytag", "Bosch", "Kenmore", "Amana",
                "Electrolux", "Dacor", "Jenn-Air", "Admiral", "Roper", "GE",
            ]
            # The URL contains the brand name between hyphens, e.g. /PS3406971-Whirlpool-W10195416-...
            # Use word boundary matching to avoid "GE" matching inside "Refrigerator"
            for brand in known_brands:
                pattern = r'[-/]' + re.escape(brand) + r'[-/]'
                if re.search(pattern, url, re.I):
                    product["brand"] = brand
                    break
        except Exception:
            pass

        # --- Rating and review count ---
        try:
            # Rating: the stars element has a width % that represents the rating
            # e.g. style="width: 96%" means 96% of 5 stars = 4.8
            stars_el = soup.select_one(".rating__stars__upper")
            if stars_el:
                style = stars_el.get("style", "")
                width_match = re.search(r'width:\s*([\d.]+)%', style)
                if width_match:
                    product["rating"] = round(float(width_match.group(1)) / 100 * 5, 1)

            # Review count like "404 Reviews"
            review_els = soup.find_all(string=re.compile(r'\d+\s*Reviews?', re.I))
            for rev_el in review_els:
                rev_match = re.search(r'(\d+)\s*Reviews?', rev_el, re.I)
                if rev_match:
                    product["review_count"] = int(rev_match.group(1))
                    break
        except Exception:
            pass

        # --- Symptoms ("Fixes these symptoms") ---
        try:
            symptoms = []

            # Method 1: Find the "Fixes these symptoms" div by ID pattern (e.g. id="3406971_Symptoms")
            symptoms_div = soup.find("div", id=re.compile(r'_Symptoms$'))
            if symptoms_div:
                # The symptom items are siblings or nearby elements after the header
                parent = symptoms_div.parent
                if parent:
                    for item in parent.find_all(["a", "li", "span", "div"]):
                        text = item.get_text(strip=True)
                        if (text
                                and len(text) > 2
                                and len(text) < 100
                                and text.lower() not in ("see more...", "see more", "fixes these symptoms", "symptoms")):
                            symptoms.append(text)

            # Method 2: Find "This part fixes the following symptoms" (expanded view)
            if not symptoms:
                fixes_header = soup.find(string=re.compile(r'This part fixes the following symptoms', re.I))
                if fixes_header:
                    container = fixes_header.parent
                    if container:
                        for item in container.find_next_siblings():
                            for el in item.find_all(["a", "li", "span", "div"]):
                                text = el.get_text(strip=True)
                                if text and len(text) > 2 and len(text) < 100:
                                    symptoms.append(text)
                            if len(symptoms) > 0:
                                break

            if symptoms:
                product["symptoms"] = list(set(symptoms))[:15]
        except Exception:
            pass

        # --- Installation info ---
        try:
            installation = {}

            # Difficulty level
            diff_el = soup.find(string=re.compile(r'Difficulty Level', re.I))
            if diff_el:
                parent = diff_el.parent
                if parent:
                    next_text = parent.find_next_sibling()
                    if next_text:
                        installation["difficulty"] = next_text.get_text(strip=True)
                    else:
                        # Might be in the same parent
                        full_text = parent.parent.get_text(strip=True) if parent.parent else ""
                        diff_match = re.search(r'Difficulty Level[:\s]*(.+?)(?:Total|Tools|$)', full_text)
                        if diff_match:
                            installation["difficulty"] = diff_match.group(1).strip()

            # Total repair time
            time_el = soup.find(string=re.compile(r'Total Repair Time', re.I))
            if time_el:
                parent = time_el.parent
                if parent:
                    next_text = parent.find_next_sibling()
                    if next_text:
                        installation["time"] = next_text.get_text(strip=True)
                    else:
                        full_text = parent.parent.get_text(strip=True) if parent.parent else ""
                        time_match = re.search(r'Total Repair Time[:\s]*(.+?)(?:Tools|Difficulty|$)', full_text)
                        if time_match:
                            installation["time"] = time_match.group(1).strip()

            # Tools needed
            tools_el = soup.find(string=re.compile(r'Tools:', re.I))
            if tools_el:
                parent = tools_el.parent
                if parent:
                    next_text = parent.find_next_sibling()
                    if next_text:
                        installation["tools"] = next_text.get_text(strip=True)
                    else:
                        full_text = parent.parent.get_text(strip=True) if parent.parent else ""
                        tools_match = re.search(r'Tools[:\s]*(.+?)(?:Difficulty|Total|$)', full_text)
                        if tools_match:
                            installation["tools"] = tools_match.group(1).strip()

            if installation:
                product["installation"] = installation
        except Exception:
            pass

        # --- Customer Repair Story (top story from "Customer Repair Stories" section) ---
        # PartSelect HTML structure (confirmed via inspection):
        #   div.repair-story          — each story container
        #   div.repair-story__title   — story headline
        #   div.repair-story__instruction — step-by-step text
        try:
            first_story = soup.select_one("div.repair-story")
            if first_story:
                title_el = first_story.select_one("div.repair-story__title")
                instr_el = first_story.select_one("div.repair-story__instruction")
                story_title = title_el.get_text(strip=True) if title_el else None
                raw_text = instr_el.get_text(strip=True) if instr_el else None
                if raw_text:
                    raw_text = re.sub(r'\s*Other Parts Used:.*$', '', raw_text, flags=re.DOTALL).strip()
                story_text = raw_text[:600] if raw_text else None

                if story_title or story_text:
                    if "installation" not in product:
                        product["installation"] = {}
                    if story_title:
                        product["installation"]["repair_story_title"] = story_title
                    if story_text:
                        product["installation"]["repair_story_text"] = story_text
        except Exception:
            pass

        # --- Image URL ---
        # Product images are served from an Azure CDN and may be JS-rendered.
        # We look for img src containing the PS number digits on the CDN.
        # BeautifulSoup may not see JS-loaded images, so we also use page.evaluate.
        try:
            ps_digits = ps_match.group(1)  # e.g. "3406971" from "PS3406971"

            # Method 1: Check BeautifulSoup-parsed HTML
            for img in soup.find_all("img"):
                src = img.get("src") or img.get("data-src") or ""
                if ps_digits in src and "azurefd.net" in src and src.endswith(".jpg"):
                    product["image_url"] = src
                    break

            # Method 2: If BS4 didn't find it, use JS to check rendered DOM
            if "image_url" not in product:
                img_url = await page.evaluate('''(digits) => {
                    const imgs = document.querySelectorAll('img');
                    for (const img of imgs) {
                        const src = img.src || '';
                        if (src.includes(digits) && src.includes('azurefd.net') && src.endsWith('.jpg')) {
                            return src;
                        }
                    }
                    return null;
                }''', ps_digits)
                if img_url:
                    product["image_url"] = img_url
        except Exception:
            pass

        return product

    except Exception as e:
        print(f"  ERROR scraping {url}: {e}")
        return None


# ---------------------------------------------------------------------------
# Step 3: Build Index Files
# ---------------------------------------------------------------------------

def build_products_index(parts_list):
    """Convert list of parts to a dictionary keyed by part number."""

    products = {}
    for part in parts_list:
        pn = part.get("part_number")
        if pn:
            products[pn] = part
    return products


def build_model_to_parts_index(parts_list):
    """Build a reverse index: model number → list of compatible part numbers."""

    model_map = defaultdict(list)

    for part in parts_list:
        part_number = part.get("part_number")
        if not part_number:
            continue

        for model in part.get("compatible_models", []):
            clean_model = model.strip().upper()
            if part_number not in model_map[clean_model]:
                model_map[clean_model].append(part_number)

    return dict(model_map)


# ---------------------------------------------------------------------------
# Step 4: Save Helpers
# ---------------------------------------------------------------------------

def save_progress(parts_list, filename="scraped_parts.json"):
    """Save current progress to disk."""

    path = OUTPUT_DIR / filename
    with open(path, "w") as f:
        json.dump(parts_list, f, indent=2)
    print(f"  Saved {len(parts_list)} parts to {path}")


def save_final_outputs(parts_list):
    """Build and save all output files."""

    # 1. Raw scraped list
    save_progress(parts_list, "scraped_parts.json")

    # 2. Products indexed by part number
    products = build_products_index(parts_list)
    with open(OUTPUT_DIR / "products.json", "w") as f:
        json.dump(products, f, indent=2)
    print(f"  Saved {len(products)} products to data/products.json")

    # 3. Model-to-parts reverse index
    model_map = build_model_to_parts_index(parts_list)
    with open(OUTPUT_DIR / "model_to_parts.json", "w") as f:
        json.dump(model_map, f, indent=2)
    print(f"  Saved {len(model_map)} model mappings to data/model_to_parts.json")


# ---------------------------------------------------------------------------
# Main Scraper
# ---------------------------------------------------------------------------

async def run():
    """Main scraping pipeline."""

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    all_parts = []
    seen_part_numbers = set()

    async with async_playwright() as p:
        browser, context, page = await create_browser(p)

        for category, category_url in CATEGORY_URLS.items():
            print(f"\n{'='*60}")
            print(f"Scraping {category.upper()} parts...")
            print(f"{'='*60}")

            # Collect product URLs from main category page
            print(f"  Collecting product URLs from {category_url}...")
            product_urls = await collect_product_urls(page, category_url)
            print(f"  Found {len(product_urls)} product URLs on main page")

            # Also check brand pages for more products
            print(f"  Collecting brand page URLs...")
            brand_urls = await collect_brand_page_urls(page, category_url, category)
            print(f"  Found {len(brand_urls)} brand pages")

            for brand_url in brand_urls[:30]:  # Check more brand pages for products
                brand_parts = await collect_product_urls(page, brand_url)
                for url in brand_parts:
                    if url not in product_urls:
                        product_urls.append(url)

            print(f"  Total unique product URLs: {len(product_urls)}")

            # Cap the number of products per category
            product_urls = product_urls[:MAX_PARTS_PER_CATEGORY]
            print(f"  Scraping {len(product_urls)} products (capped at {MAX_PARTS_PER_CATEGORY})...")

            # Scrape each product page
            for i, url in enumerate(product_urls):
                # Extract part number from URL to check for duplicates
                ps_match = re.search(r'PS(\d+)', url)
                if ps_match:
                    pn = f"PS{ps_match.group(1)}"
                    if pn in seen_part_numbers:
                        continue
                    seen_part_numbers.add(pn)

                print(f"  [{i+1}/{len(product_urls)}] {url[:80]}...")
                product = await scrape_product_page(page, url)

                if product:
                    product["category"] = category
                    product["appliance_type"] = category  # e.g. "refrigerator" or "dishwasher"
                    all_parts.append(product)

                    # Show what we got
                    fields = [k for k in product.keys() if product[k] is not None]
                    print(f"    ✓ {product.get('title', '?')[:50]} | Fields: {len(fields)}")
                else:
                    print(f"    ✗ Failed to scrape")

                # Save progress periodically
                if len(all_parts) % SAVE_EVERY == 0 and len(all_parts) > 0:
                    save_progress(all_parts)

        await browser.close()

    # Final save
    print(f"\n{'='*60}")
    print(f"Scraping complete! Total products: {len(all_parts)}")
    print(f"{'='*60}")

    save_final_outputs(all_parts)

    # Print summary
    fridge = [p for p in all_parts if p.get("category") == "refrigerator"]
    dish = [p for p in all_parts if p.get("category") == "dishwasher"]
    with_price = [p for p in all_parts if p.get("price")]
    with_symptoms = [p for p in all_parts if p.get("symptoms")]
    with_install = [p for p in all_parts if p.get("installation")]
    with_rating = [p for p in all_parts if p.get("rating")]

    print(f"\n  Refrigerator parts: {len(fridge)}")
    print(f"  Dishwasher parts:   {len(dish)}")
    print(f"  With price:         {len(with_price)}/{len(all_parts)}")
    print(f"  With symptoms:      {len(with_symptoms)}/{len(all_parts)}")
    print(f"  With installation:  {len(with_install)}/{len(all_parts)}")
    print(f"  With rating:        {len(with_rating)}/{len(all_parts)}")


if __name__ == "__main__":
    asyncio.run(run())
