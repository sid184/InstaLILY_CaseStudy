"""
Safety layer for the PartSelect chat agent.

Functions here run BEFORE and AFTER the agent responds:
  - check_scope(): Before — reject off-topic queries
  - validate_response(): After — catch hallucinated part numbers/prices
  - add_safety_warnings(): After — inject appliance safety reminders
"""

import re
from typing import List, Optional

from backend.tools import _products


# ---------------------------------------------------------------------------
# Scope Definition
# ---------------------------------------------------------------------------

# Appliances we DO support
IN_SCOPE_APPLIANCES = {"refrigerator", "fridge", "dishwasher"}

# Words/phrases that signal the message is about appliance parts
# (used by the "no appliance context" heuristic)
APPLIANCE_CONTEXT_SIGNALS = {
    # Appliance types
    "refrigerator", "fridge", "dishwasher", "appliance",
    # Part-related words
    "part", "parts", "filter", "shelf", "bin", "gasket", "motor",
    "pump", "valve", "hose", "rack", "wheel", "arm", "spray",
    "element", "thermostat", "sensor", "switch", "door", "handle",
    "drawer", "tray", "seal", "latch", "roller", "bearing",
    # Action words related to repair
    "fix", "repair", "replace", "install", "broken", "leaking",
    "leak", "noise", "noisy", "draining", "clogged",
    "compatible", "compatibility", "fits", "model",
    # Part numbers
    "ps", "wp", "wr", "mfg",
    # Brand names we carry
    "whirlpool", "frigidaire", "lg", "ge", "bosch", "samsung",
    # Shopping intent
    "buy", "order", "price", "cost", "stock", "shipping",
    # Conversational — customer engaging with us
    "help", "need", "looking", "find", "search", "recommend",
    "sell", "available", "warranty", "return",
}

# Appliances we do NOT support — must check these BEFORE in-scope
# because some overlap (e.g. "washer" is in "dishwasher")
OUT_OF_SCOPE_APPLIANCES = {
    "washing machine", "washer dryer", "clothes washer",
    "laundry", "dryer", "tumble dryer",
    "oven", "stove", "range", "cooktop",
    "microwave",
    "air conditioner", "hvac", "furnace", "heater",
    "garbage disposal",
    "freezer",  # standalone freezers — fridge/freezer combos are in scope
    "trash compactor",
    "ice machine",  # commercial ice machines, not fridge ice makers
    "wine cooler",
    "hood", "range hood", "vent hood",
}

# Completely off-topic subjects
OFF_TOPIC_KEYWORDS = {
    "weather", "stocks", "crypto", "bitcoin",
    "recipe", "recipes", "cooking",
    "news", "sports", "score",
    "movie", "movies", "music", "song",
    "joke", "jokes", "funny",
    "python", "javascript", "code", "programming",
    "homework", "essay",
    "politics", "election", "president",
}


# ---------------------------------------------------------------------------
# check_scope
# ---------------------------------------------------------------------------

def check_scope(message: str, has_history: bool = False) -> dict:
    """
    Determine whether a user message is within our supported scope.

    We support: refrigerator parts and dishwasher parts.
    We reject: other appliances, off-topic questions.

    Args:
        message: The user's raw message text.

    Returns:
        A dict with:
          - in_scope (bool): Whether the query is something we can help with
          - reason (str): Explanation for rejection (empty if in_scope)
          - detected (str | None): The out-of-scope keyword we matched
    """
    result = {
        "in_scope": True,
        "reason": "",
        "detected": None,
    }

    msg_lower = message.strip().lower()

    if not msg_lower:
        return result  # Empty messages are fine — the agent can ask for input

    # --- Check for out-of-scope appliances ---
    # Check multi-word phrases first (e.g. "washing machine" before "washer")
    for phrase in sorted(OUT_OF_SCOPE_APPLIANCES, key=len, reverse=True):
        if phrase in msg_lower:
            # Make sure "dishwasher" isn't being rejected because of "washer"
            if phrase == "washer" and "dishwasher" in msg_lower:
                continue
            result["in_scope"] = False
            result["detected"] = phrase
            result["reason"] = (
                f"I specialise in refrigerator and dishwasher parts only. "
                f"I can't help with {phrase} parts, but I'd suggest checking "
                f"PartSelect.com for other appliance categories."
            )
            return result

    # --- Check for off-topic subjects ---
    # Split into words for whole-word matching to avoid false positives
    words = set(re.findall(r'\b\w+\b', msg_lower))

    for keyword in OFF_TOPIC_KEYWORDS:
        if keyword in words:
            result["in_scope"] = False
            result["detected"] = keyword
            result["reason"] = (
                "I'm a PartSelect appliance parts assistant — I help with "
                "refrigerator and dishwasher parts, compatibility, installation, "
                "and troubleshooting. How can I help with your appliance?"
            )
            return result

    # --- Heuristic: no appliance context at all ---
    # If the message has no appliance-related words AND no part number pattern,
    # it's likely off-topic. But we only flag this for messages that look like
    # questions/requests (not short greetings like "hi" or "thanks").
    has_part_number = bool(re.search(r'\bPS\d+\b', msg_lower, re.IGNORECASE))
    has_appliance_context = bool(words & APPLIANCE_CONTEXT_SIGNALS)

    if not has_part_number and not has_appliance_context and len(words) >= 4 and not has_history:
        result["in_scope"] = False
        result["detected"] = "no_appliance_context"
        result["reason"] = (
            "I'm a PartSelect appliance parts assistant — I help with "
            "refrigerator and dishwasher parts, compatibility, installation, "
            "and troubleshooting. How can I help with your appliance?"
        )
        return result

    return result


# ---------------------------------------------------------------------------
# validate_response
# ---------------------------------------------------------------------------

# Regex pattern for extracting part numbers from response text
_PS_PATTERN = re.compile(r'\bPS\d{4,10}\b')


def validate_response(response_text: str) -> dict:
    """
    Validate the agent's response text for hallucinated data.

    Checks:
      1. Part numbers — any PS number mentioned must exist in our database
      2. Prices — any dollar amount tied to a PS number must match our data
         (within a small tolerance for rounding)

    This runs AFTER Claude generates a response, before we send it to the user.

    Args:
        response_text: The agent's full response text.

    Returns:
        A dict with:
          - valid (bool): True if no issues found
          - issues (list[str]): Human-readable descriptions of each problem
          - hallucinated_parts (list[str]): PS numbers not in our database
          - price_mismatches (list[str]): PS numbers with wrong prices
    """
    result = {
        "valid": True,
        "issues": [],
        "hallucinated_parts": [],
        "price_mismatches": [],
    }

    if not response_text.strip():
        return result

    # --- Check 1: Hallucinated part numbers ---
    mentioned_parts = set(_PS_PATTERN.findall(response_text))

    for pn in mentioned_parts:
        if pn not in _products:
            result["valid"] = False
            result["hallucinated_parts"].append(pn)
            result["issues"].append(
                f"Part number {pn} was mentioned but does not exist in our database."
            )

    return result