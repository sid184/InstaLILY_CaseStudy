"""
Tests for backend/tools.py

Run:  source venv/bin/activate && python -m pytest backend/tests/test_tools.py -v
"""

import pytest
from backend.tools import search_products, check_compatibility, get_installation_guide, diagnose_problem, get_related_parts, _products, _model_to_parts
from backend.models import Installation, Product


# ---------------------------------------------------------------------------
# Data Loading
# ---------------------------------------------------------------------------

class TestDataLoading:
    """Verify that product data loaded correctly at import time."""

    def test_products_loaded(self):
        assert len(_products) > 0, "No products loaded"

    def test_products_count(self):
        assert len(_products) == 119

    def test_model_to_parts_loaded(self):
        assert len(_model_to_parts) > 0, "No model mappings loaded"

    def test_product_has_required_fields(self):
        product = list(_products.values())[0]
        for field in ["part_number", "title", "price", "brand", "appliance_type", "url"]:
            assert field in product, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# search_products: Exact Part Number Match
# ---------------------------------------------------------------------------

class TestSearchByPartNumber:
    """Test Strategy 1: exact part number lookup."""

    def test_exact_ps_number(self):
        results = search_products("PS3406971")
        assert len(results) == 1
        assert results[0].part_number == "PS3406971"

    def test_case_insensitive(self):
        results = search_products("ps3406971")
        assert len(results) == 1
        assert results[0].part_number == "PS3406971"

    def test_bare_digits(self):
        """User types just digits without PS prefix."""
        results = search_products("3406971")
        assert len(results) == 1
        assert results[0].part_number == "PS3406971"

    def test_with_whitespace(self):
        results = search_products("  PS3406971  ")
        assert len(results) == 1

    def test_nonexistent_part_number(self):
        """A PS number that doesn't exist should fall through to vector search."""
        results = search_products("PS0000000")
        # Won't get an exact match, but vector search may return results
        assert all(isinstance(r, Product) for r in results)

    def test_returns_product_model(self):
        results = search_products("PS3406971")
        assert isinstance(results[0], Product)
        assert results[0].price > 0
        assert results[0].brand != ""


# ---------------------------------------------------------------------------
# search_products: Manufacturer Part Number Match
# ---------------------------------------------------------------------------

class TestSearchByManufacturerPart:
    """Test Strategy 2: manufacturer part number lookup."""

    def test_manufacturer_part_number(self):
        results = search_products("W10195416")
        assert len(results) == 1
        assert results[0].part_number == "PS3406971"
        assert results[0].manufacturer_part_number == "W10195416"

    def test_manufacturer_part_case_insensitive(self):
        results = search_products("w10195416")
        assert len(results) == 1


# ---------------------------------------------------------------------------
# search_products: Vector Search (Natural Language)
# ---------------------------------------------------------------------------

class TestSearchVectorQuery:
    """Test Strategy 3: ChromaDB vector search."""

    def test_symptom_query(self):
        results = search_products("refrigerator is leaking")
        assert len(results) > 0
        # At least one result should have "Leaking" in symptoms
        has_leaking = any(
            any("leak" in s.lower() for s in r.symptoms)
            for r in results
        )
        assert has_leaking, "Expected at least one result with leaking symptom"

    def test_part_type_query(self):
        results = search_products("dishwasher spray arm")
        assert len(results) > 0
        # Results should be dishwasher parts with "spray arm" in the title
        has_spray_arm = any("spray arm" in r.title.lower() for r in results)
        assert has_spray_arm

    def test_brand_query(self):
        results = search_products("Whirlpool water filter")
        assert len(results) > 0
        # At least first result should be Whirlpool
        has_whirlpool = any(r.brand == "Whirlpool" for r in results)
        assert has_whirlpool

    def test_returns_up_to_top_k(self):
        results = search_products("door shelf", top_k=3)
        assert len(results) <= 3

    def test_default_top_k_is_5(self):
        results = search_products("refrigerator part")
        assert len(results) <= 5


# ---------------------------------------------------------------------------
# search_products: Appliance Type Filter
# ---------------------------------------------------------------------------

class TestSearchWithFilter:
    """Test the appliance_type filter."""

    def test_filter_refrigerator(self):
        results = search_products("water filter", appliance_type="refrigerator")
        assert len(results) > 0
        assert all(r.appliance_type == "refrigerator" for r in results)

    def test_filter_dishwasher(self):
        results = search_products("heating element", appliance_type="dishwasher")
        assert len(results) > 0
        assert all(r.appliance_type == "dishwasher" for r in results)

    def test_filter_case_insensitive(self):
        results = search_products("spray arm", appliance_type="Dishwasher")
        assert len(results) > 0
        assert all(r.appliance_type == "dishwasher" for r in results)

    def test_exact_match_respects_filter(self):
        """PS3406971 is a dishwasher part. Filtering for refrigerator should exclude it
        from exact match, falling through to vector search for refrigerator parts."""
        results = search_products("PS3406971", appliance_type="refrigerator")
        # The exact dishwasher part should NOT be in results
        assert all(r.part_number != "PS3406971" for r in results)
        # All results should be refrigerator parts
        assert all(r.appliance_type == "refrigerator" for r in results)


# ---------------------------------------------------------------------------
# search_products: Edge Cases
# ---------------------------------------------------------------------------

class TestSearchEdgeCases:

    def test_empty_query(self):
        results = search_products("")
        # Should not crash, may return vector search results
        assert isinstance(results, list)

    def test_special_characters(self):
        results = search_products("door shelf (right)")
        assert isinstance(results, list)

    def test_very_long_query(self):
        results = search_products("a " * 500)
        assert isinstance(results, list)

    def test_all_results_are_product_models(self):
        results = search_products("gasket")
        for r in results:
            assert isinstance(r, Product)
            assert r.part_number.startswith("PS")
            assert r.price > 0


# ---------------------------------------------------------------------------
# check_compatibility: Compatible Matches
# ---------------------------------------------------------------------------

class TestCompatibilityMatch:
    """Test that compatible part+model pairs are correctly identified."""

    def test_known_compatible_pair(self):
        """PS3406971 is compatible with model 2213223N414."""
        result = check_compatibility("PS3406971", "2213223N414")
        assert result["compatible"] is True
        assert result["model_found"] is True
        assert result["part"] is not None
        assert result["part"].part_number == "PS3406971"

    def test_case_insensitive_part(self):
        result = check_compatibility("ps3406971", "2213223N414")
        assert result["compatible"] is True

    def test_bare_digits_part(self):
        """User types just the digits without PS prefix."""
        result = check_compatibility("3406971", "2213223N414")
        assert result["compatible"] is True
        assert result["part"].part_number == "PS3406971"

    def test_whitespace_handling(self):
        result = check_compatibility("  PS3406971  ", "  2213223N414  ")
        assert result["compatible"] is True

    def test_returns_product_model(self):
        result = check_compatibility("PS3406971", "2213223N414")
        assert isinstance(result["part"], Product)
        assert result["part"].price > 0


# ---------------------------------------------------------------------------
# check_compatibility: Mismatches
# ---------------------------------------------------------------------------

class TestCompatibilityMismatch:
    """Test that incompatible part+model pairs are correctly identified."""

    def test_part_does_not_fit_model(self):
        """PS3406971 (dishwasher) should NOT fit FFSS2615TD0 (fridge model)."""
        result = check_compatibility("PS3406971", "FFSS2615TD0")
        assert result["compatible"] is False
        assert result["model_found"] is True
        assert result["part"] is not None  # Part still exists

    def test_mismatch_suggests_alternatives(self):
        """When part doesn't fit, we should get alternative suggestions."""
        result = check_compatibility("PS3406971", "FFSS2615TD0")
        assert result["compatible"] is False
        assert len(result["compatible_parts"]) > 0
        # Alternatives should be real Product models
        for alt in result["compatible_parts"]:
            assert isinstance(alt, Product)

    def test_alternatives_capped_at_five(self):
        """Alternatives list should have at most 5 items."""
        # Use a model with many parts
        result = check_compatibility("PS12364199", "2213223N414")
        assert len(result["compatible_parts"]) <= 5


# ---------------------------------------------------------------------------
# check_compatibility: Edge Cases
# ---------------------------------------------------------------------------

class TestCompatibilityEdgeCases:

    def test_nonexistent_part(self):
        """Part number that doesn't exist in our database."""
        result = check_compatibility("PS0000000", "2213223N414")
        assert result["part"] is None
        # Model exists, so we can still check the parts list
        assert result["model_found"] is True
        # PS0000000 won't be in the model's parts list
        assert result["compatible"] is False

    def test_nonexistent_model(self):
        """Model number that doesn't exist in our database."""
        result = check_compatibility("PS3406971", "ZZZZZZZZZ")
        assert result["model_found"] is False
        assert result["compatible"] is False
        # Part should still be looked up
        assert result["part"] is not None
        assert result["part"].part_number == "PS3406971"

    def test_both_nonexistent(self):
        """Neither part nor model exists."""
        result = check_compatibility("PS0000000", "ZZZZZZZZZ")
        assert result["part"] is None
        assert result["model_found"] is False
        assert result["compatible"] is False
        assert result["compatible_parts"] == []

    def test_empty_strings(self):
        """Empty inputs should not crash."""
        result = check_compatibility("", "")
        assert result["compatible"] is False
        assert isinstance(result, dict)

    def test_result_shape(self):
        """Every call should return the same dict shape."""
        result = check_compatibility("PS3406971", "2213223N414")
        assert "compatible" in result
        assert "part" in result
        assert "model_found" in result
        assert "compatible_parts" in result


# ---------------------------------------------------------------------------
# get_installation_guide: Part With Full Installation Info
# ---------------------------------------------------------------------------

class TestInstallationGuideFound:
    """Test parts that have installation data."""

    def test_full_installation(self):
        """PS11701542 has difficulty, time, and tools."""
        result = get_installation_guide("PS11701542")
        assert result["found"] is True
        assert result["has_guide"] is True
        assert isinstance(result["installation"], Installation)
        assert result["installation"].difficulty == "Easy"
        assert result["installation"].time == "Less than 15 mins"
        assert result["installation"].tools is not None

    def test_partial_installation(self):
        """PS12364199 has difficulty and time but no tools."""
        result = get_installation_guide("PS12364199")
        assert result["found"] is True
        assert result["has_guide"] is True
        assert result["installation"].difficulty == "Really Easy"
        assert result["installation"].time == "30 - 60 mins"
        assert result["installation"].tools is None

    def test_returns_title(self):
        result = get_installation_guide("PS11701542")
        assert result["title"] is not None
        assert len(result["title"]) > 0

    def test_returns_url(self):
        result = get_installation_guide("PS11701542")
        assert result["url"] is not None
        assert result["url"].startswith("https://")

    def test_case_insensitive(self):
        result = get_installation_guide("ps11701542")
        assert result["found"] is True
        assert result["has_guide"] is True

    def test_bare_digits(self):
        result = get_installation_guide("11701542")
        assert result["found"] is True
        assert result["has_guide"] is True

    def test_whitespace(self):
        result = get_installation_guide("  PS11701542  ")
        assert result["found"] is True


# ---------------------------------------------------------------------------
# get_installation_guide: Part Without Installation Info
# ---------------------------------------------------------------------------

class TestInstallationGuideNoInfo:
    """Test parts that exist but have no installation data."""

    def test_no_installation_data(self):
        """PS16662677 exists but has no installation info."""
        result = get_installation_guide("PS16662677")
        assert result["found"] is True
        assert result["has_guide"] is False
        assert result["installation"] is None
        # Part info is still returned
        assert result["title"] is not None
        assert result["url"] is not None


# ---------------------------------------------------------------------------
# get_installation_guide: Edge Cases
# ---------------------------------------------------------------------------

class TestInstallationGuideEdgeCases:

    def test_nonexistent_part(self):
        result = get_installation_guide("PS0000000")
        assert result["found"] is False
        assert result["has_guide"] is False
        assert result["installation"] is None
        assert result["part_number"] == "PS0000000"

    def test_empty_string(self):
        result = get_installation_guide("")
        assert result["found"] is False
        assert isinstance(result, dict)

    def test_result_shape(self):
        """Every call returns the same dict shape."""
        result = get_installation_guide("PS11701542")
        assert "found" in result
        assert "part_number" in result
        assert "title" in result
        assert "installation" in result
        assert "has_guide" in result
        assert "url" in result


# ---------------------------------------------------------------------------
# diagnose_problem: Exact Symptom Match
# ---------------------------------------------------------------------------

class TestDiagnoseExactMatch:
    """Test Strategy 1: matching against the symptoms lists in product data."""

    def test_exact_symptom_string(self):
        """'Leaking' is the most common symptom (46 parts)."""
        result = diagnose_problem("Leaking")
        assert result["strategy"] == "exact"
        assert result["matched_symptom"] is not None
        assert len(result["parts"]) > 0

    def test_case_insensitive(self):
        result = diagnose_problem("leaking")
        assert result["strategy"] == "exact"
        assert len(result["parts"]) > 0

    def test_partial_match(self):
        """'ice maker' should match symptoms like 'Ice maker not making ice'."""
        result = diagnose_problem("ice maker")
        assert result["strategy"] == "exact"
        assert len(result["parts"]) > 0

    def test_results_are_product_models(self):
        result = diagnose_problem("Leaking")
        for p in result["parts"]:
            assert isinstance(p, Product)
            assert p.part_number.startswith("PS")

    def test_matched_symptom_is_canonical(self):
        """The matched_symptom should be the full symptom string, not the user input."""
        result = diagnose_problem("ice maker")
        assert result["matched_symptom"] is not None
        # Should be a full symptom like "Ice maker not making ice", not "ice maker"
        assert len(result["matched_symptom"]) > len("ice maker")

    def test_respects_top_k(self):
        result = diagnose_problem("Leaking", top_k=3)
        assert len(result["parts"]) <= 3


# ---------------------------------------------------------------------------
# diagnose_problem: Appliance Type Filter
# ---------------------------------------------------------------------------

class TestDiagnoseWithFilter:
    """Test the appliance_type filter on diagnose_problem."""

    def test_filter_refrigerator(self):
        result = diagnose_problem("Leaking", appliance_type="refrigerator")
        assert len(result["parts"]) > 0
        assert all(p.appliance_type == "refrigerator" for p in result["parts"])

    def test_filter_dishwasher(self):
        result = diagnose_problem("Leaking", appliance_type="dishwasher")
        assert len(result["parts"]) > 0
        assert all(p.appliance_type == "dishwasher" for p in result["parts"])

    def test_filter_case_insensitive(self):
        result = diagnose_problem("Leaking", appliance_type="Refrigerator")
        assert len(result["parts"]) > 0
        assert all(p.appliance_type == "refrigerator" for p in result["parts"])


# ---------------------------------------------------------------------------
# diagnose_problem: Vector Search Fallback
# ---------------------------------------------------------------------------

class TestDiagnoseVectorFallback:
    """Test Strategy 2: when no exact symptom match, fall back to vector search."""

    def test_natural_language_query(self):
        """A conversational description that won't match any symptom string exactly."""
        result = diagnose_problem("my fridge is making a weird humming noise")
        assert len(result["parts"]) > 0
        assert result["strategy"] == "vector"

    def test_vague_description(self):
        result = diagnose_problem("something is wrong with the door")
        assert len(result["parts"]) > 0


# ---------------------------------------------------------------------------
# diagnose_problem: Edge Cases
# ---------------------------------------------------------------------------

class TestDiagnoseEdgeCases:

    def test_empty_string(self):
        result = diagnose_problem("")
        assert result["parts"] == []
        assert result["strategy"] == "none"

    def test_whitespace_only(self):
        result = diagnose_problem("   ")
        assert result["parts"] == []
        assert result["strategy"] == "none"

    def test_gibberish(self):
        """Random text should not crash, may return vector results."""
        result = diagnose_problem("xyzzy foobar 12345")
        assert isinstance(result["parts"], list)

    def test_result_shape(self):
        """Every call returns the same dict shape."""
        result = diagnose_problem("Leaking")
        assert "matched_symptom" in result
        assert "parts" in result
        assert "strategy" in result


# ---------------------------------------------------------------------------
# get_related_parts: Model Overlap (Strategy 1)
# ---------------------------------------------------------------------------

class TestRelatedPartsModelOverlap:
    """Test Strategy 1: finding parts that share compatible models."""

    def test_finds_related_parts(self):
        """PS3406971 has 30 compatible models — should find parts sharing them."""
        result = get_related_parts("PS3406971")
        assert result["found"] is True
        assert result["strategy"] == "model_overlap"
        assert len(result["related"]) > 0

    def test_related_parts_are_different(self):
        """Related parts should NOT include the input part itself."""
        result = get_related_parts("PS3406971")
        for r in result["related"]:
            assert r.part_number != "PS3406971"

    def test_related_parts_are_product_models(self):
        result = get_related_parts("PS3406971")
        for r in result["related"]:
            assert isinstance(r, Product)
            assert r.part_number.startswith("PS")
            assert r.price > 0

    def test_returns_input_part(self):
        """The result should include the original part for context."""
        result = get_related_parts("PS3406971")
        assert result["part"] is not None
        assert result["part"].part_number == "PS3406971"

    def test_respects_top_k(self):
        result = get_related_parts("PS3406971", top_k=3)
        assert len(result["related"]) <= 3

    def test_most_related_first(self):
        """Parts sharing more models should appear earlier in the list."""
        result = get_related_parts("PS3406971", top_k=10)
        if len(result["related"]) >= 2:
            # The first result should share at least as many models as the last
            # (We can't verify exact counts easily, but we can check ordering
            # by re-computing overlap for first and last)
            first_pn = result["related"][0].part_number
            last_pn = result["related"][-1].part_number
            models = set(_products["PS3406971"].get("compatible_models", []))
            first_shared = len(models & set(_products[first_pn].get("compatible_models", [])))
            last_shared = len(models & set(_products[last_pn].get("compatible_models", [])))
            assert first_shared >= last_shared


# ---------------------------------------------------------------------------
# get_related_parts: Same Category Fallback (Strategy 2)
# ---------------------------------------------------------------------------

class TestRelatedPartsCategoryFallback:
    """Test Strategy 2: fallback to same appliance_type + brand."""

    def test_fallback_for_part_without_models(self):
        """PS3637058 has no compatible_models — should fall back to same category."""
        result = get_related_parts("PS3637058")
        assert result["found"] is True
        assert result["strategy"] == "same_category"
        assert len(result["related"]) > 0

    def test_fallback_same_type_and_brand(self):
        """Fallback results should share the same appliance_type and brand."""
        result = get_related_parts("PS3637058")
        source = _products["PS3637058"]
        for r in result["related"]:
            assert r.appliance_type == source["appliance_type"]
            assert r.brand == source["brand"]


# ---------------------------------------------------------------------------
# get_related_parts: Input Normalisation
# ---------------------------------------------------------------------------

class TestRelatedPartsInput:

    def test_case_insensitive(self):
        result = get_related_parts("ps3406971")
        assert result["found"] is True
        assert len(result["related"]) > 0

    def test_bare_digits(self):
        result = get_related_parts("3406971")
        assert result["found"] is True

    def test_whitespace(self):
        result = get_related_parts("  PS3406971  ")
        assert result["found"] is True


# ---------------------------------------------------------------------------
# get_related_parts: Edge Cases
# ---------------------------------------------------------------------------

class TestRelatedPartsEdgeCases:

    def test_nonexistent_part(self):
        result = get_related_parts("PS0000000")
        assert result["found"] is False
        assert result["part"] is None
        assert result["related"] == []
        assert result["strategy"] == "none"

    def test_empty_string(self):
        result = get_related_parts("")
        assert result["found"] is False
        assert isinstance(result, dict)

    def test_result_shape(self):
        """Every call returns the same dict shape."""
        result = get_related_parts("PS3406971")
        assert "found" in result
        assert "part" in result
        assert "related" in result
        assert "strategy" in result
