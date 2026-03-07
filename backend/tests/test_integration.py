"""
Integration tests — simulate realistic customer journeys through all 5 tools.

These tests use real scraped data and exercise the tools in the order
a chatbot conversation would actually call them.

Run:  source venv/bin/activate && python -m pytest backend/tests/test_integration.py -v
"""

import json
from pathlib import Path

import pytest
from backend.models import Installation, Product
from backend.tools import (
    search_products,
    check_compatibility,
    get_installation_guide,
    diagnose_problem,
    get_related_parts,
    _products,
    _model_to_parts,
)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


# ---------------------------------------------------------------------------
# Scenario 1: Customer knows the part number
# "I need part PS3406971 — does it fit my model 2213223N414?
#  How do I install it? What else might I need?"
# ---------------------------------------------------------------------------

class TestScenarioKnownPartNumber:

    def test_step1_search_by_part_number(self):
        """Customer searches by exact part number."""
        results = search_products("PS3406971")
        assert len(results) == 1
        part = results[0]
        assert part.part_number == "PS3406971"
        assert part.price > 0
        assert part.brand != ""
        assert part.url.startswith("https://")

    def test_step2_check_compatibility(self):
        """Customer asks if it fits their appliance model."""
        result = check_compatibility("PS3406971", "2213223N414")
        assert result["compatible"] is True
        assert result["part"].part_number == "PS3406971"

    def test_step3_get_installation_guide(self):
        """Customer asks how to install it."""
        result = get_installation_guide("PS3406971")
        assert result["found"] is True
        # Part may or may not have installation info, but should not crash
        assert isinstance(result["has_guide"], bool)

    def test_step4_get_related_parts(self):
        """Customer asks what else they might need."""
        result = get_related_parts("PS3406971")
        assert result["found"] is True
        assert len(result["related"]) > 0
        # Related parts should be different from the input
        for r in result["related"]:
            assert r.part_number != "PS3406971"

    def test_full_journey(self):
        """All steps chained together — the output of one informs the next."""
        # Step 1: Search
        results = search_products("PS3406971")
        part = results[0]

        # Step 2: Check compatibility with a known model
        models = part.compatible_models
        if models:
            compat = check_compatibility(part.part_number, models[0])
            assert compat["compatible"] is True

        # Step 3: Installation
        guide = get_installation_guide(part.part_number)
        assert guide["found"] is True

        # Step 4: Related parts
        related = get_related_parts(part.part_number)
        assert related["found"] is True


# ---------------------------------------------------------------------------
# Scenario 2: Customer describes a symptom
# "My dishwasher is leaking — what part do I need?
#  Does it fit my model? How hard is the install?"
# ---------------------------------------------------------------------------

class TestScenarioSymptomDiagnosis:

    def test_step1_diagnose_problem(self):
        """Customer describes a symptom."""
        result = diagnose_problem("leaking", appliance_type="dishwasher")
        assert len(result["parts"]) > 0
        assert all(p.appliance_type == "dishwasher" for p in result["parts"])

    def test_step2_check_first_suggestion(self):
        """Take the first suggestion and check compatibility with a model."""
        diag = diagnose_problem("leaking", appliance_type="dishwasher")
        suggested_part = diag["parts"][0]

        # Find a model this part is compatible with
        if suggested_part.compatible_models:
            model = suggested_part.compatible_models[0]
            compat = check_compatibility(suggested_part.part_number, model)
            assert compat["compatible"] is True

    def test_step3_installation_for_suggestion(self):
        """Check installation details for the suggested part."""
        diag = diagnose_problem("leaking", appliance_type="dishwasher")
        suggested_part = diag["parts"][0]
        guide = get_installation_guide(suggested_part.part_number)
        assert guide["found"] is True

    def test_full_journey(self):
        """Symptom → diagnose → pick part → compatibility → install → related."""
        # Step 1: Diagnose
        diag = diagnose_problem("leaking", appliance_type="dishwasher")
        assert len(diag["parts"]) > 0
        part = diag["parts"][0]

        # Step 2: Compatibility (with first compatible model)
        if part.compatible_models:
            compat = check_compatibility(part.part_number, part.compatible_models[0])
            assert compat["compatible"] is True

        # Step 3: Installation
        guide = get_installation_guide(part.part_number)
        assert guide["found"] is True

        # Step 4: Related parts
        related = get_related_parts(part.part_number)
        assert related["found"] is True


# ---------------------------------------------------------------------------
# Scenario 3: Customer searches by keyword
# "I need a water filter for my Whirlpool refrigerator"
# ---------------------------------------------------------------------------

class TestScenarioKeywordSearch:

    def test_step1_search_with_filter(self):
        """Natural language search with appliance filter."""
        results = search_products("water filter", appliance_type="refrigerator")
        assert len(results) > 0
        assert all(r.appliance_type == "refrigerator" for r in results)

    def test_step2_pick_and_check_compatibility(self):
        """Pick a result and check if it fits a model."""
        results = search_products("water filter", appliance_type="refrigerator")
        part = results[0]

        if part.compatible_models:
            compat = check_compatibility(part.part_number, part.compatible_models[0])
            assert compat["compatible"] is True

    def test_step3_brand_filter_works(self):
        """Search for a specific brand."""
        results = search_products("Whirlpool water filter")
        assert len(results) > 0
        has_whirlpool = any(r.brand == "Whirlpool" for r in results)
        assert has_whirlpool


# ---------------------------------------------------------------------------
# Scenario 4: Incompatible part — suggest alternatives
# "Does PS3406971 (dishwasher part) fit my FFSS2615TD0 (fridge model)?"
# ---------------------------------------------------------------------------

class TestScenarioIncompatiblePart:

    def test_mismatch_detected(self):
        """Part doesn't fit the model."""
        result = check_compatibility("PS3406971", "FFSS2615TD0")
        assert result["compatible"] is False
        assert result["model_found"] is True

    def test_alternatives_suggested(self):
        """System suggests parts that DO fit the model."""
        result = check_compatibility("PS3406971", "FFSS2615TD0")
        assert len(result["compatible_parts"]) > 0
        # All alternatives should be valid products
        for alt in result["compatible_parts"]:
            assert isinstance(alt, Product)

    def test_can_search_for_correct_parts(self):
        """After mismatch, customer can search for the right appliance type."""
        # The model FFSS2615TD0 is a Frigidaire fridge
        results = search_products("dishrack wheel", appliance_type="dishwasher")
        # Should find dishwasher parts instead
        assert len(results) > 0
        assert all(r.appliance_type == "dishwasher" for r in results)


# ---------------------------------------------------------------------------
# Scenario 5: Manufacturer part number lookup
# "I have part number W10195416 on the old part — what is it?"
# ---------------------------------------------------------------------------

class TestScenarioManufacturerPartNumber:

    def test_find_by_manufacturer_number(self):
        """Search by manufacturer part number finds the right PS part."""
        results = search_products("W10195416")
        assert len(results) == 1
        part = results[0]
        assert part.manufacturer_part_number == "W10195416"
        assert part.part_number == "PS3406971"

    def test_then_get_full_details(self):
        """After finding the part, get installation and related parts."""
        results = search_products("W10195416")
        part = results[0]

        guide = get_installation_guide(part.part_number)
        assert guide["found"] is True

        related = get_related_parts(part.part_number)
        assert related["found"] is True


# ---------------------------------------------------------------------------
# Data Integrity: Every product works with every tool
# ---------------------------------------------------------------------------

class TestAllProductsWithAllTools:
    """Run every tool against every product in our database to catch any
    data issues that unit tests on specific products might miss."""

    def test_every_product_searchable_by_part_number(self):
        """Every product can be found by its PS number."""
        errors = []
        for pn in _products:
            results = search_products(pn)
            if len(results) != 1 or results[0].part_number != pn:
                errors.append(pn)
        assert errors == [], f"Failed to find: {errors}"

    def test_every_product_has_installation_guide_result(self):
        """get_installation_guide should never crash on any product."""
        errors = []
        for pn in _products:
            try:
                result = get_installation_guide(pn)
                assert result["found"] is True
            except Exception as e:
                errors.append(f"{pn}: {e}")
        assert errors == [], f"Failures:\n" + "\n".join(errors)

    def test_every_product_has_related_parts_result(self):
        """get_related_parts should never crash on any product."""
        errors = []
        for pn in _products:
            try:
                result = get_related_parts(pn)
                assert result["found"] is True
            except Exception as e:
                errors.append(f"{pn}: {e}")
        assert errors == [], f"Failures:\n" + "\n".join(errors)

    def test_model_to_parts_consistency(self):
        """Every part referenced in model_to_parts.json exists in products.json."""
        missing = []
        for model, parts in _model_to_parts.items():
            for pn in parts:
                if pn not in _products:
                    missing.append(f"{model} -> {pn}")
        assert missing == [], f"Missing products:\n" + "\n".join(missing[:10])

    def test_compatible_models_reverse_lookup(self):
        """For every product, its compatible_models should reference it back
        in model_to_parts.json."""
        mismatches = []
        for pn, product in _products.items():
            for model in product.get("compatible_models", []):
                parts_for_model = _model_to_parts.get(model, [])
                if pn not in parts_for_model:
                    mismatches.append(f"{pn} claims model {model}, but model_to_parts disagrees")
        assert mismatches == [], f"Mismatches:\n" + "\n".join(mismatches[:10])
