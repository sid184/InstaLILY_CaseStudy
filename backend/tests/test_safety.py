"""
Tests for backend/safety.py

Run:  source venv/bin/activate && python -m pytest backend/tests/test_safety.py -v
"""

import pytest
from backend.safety import check_scope, validate_response


# ---------------------------------------------------------------------------
# check_scope: In-Scope Messages
# ---------------------------------------------------------------------------

class TestCheckScopeInScope:
    """Messages that should be accepted."""

    def test_refrigerator_query(self):
        result = check_scope("refrigerator water filter")
        assert result["in_scope"] is True

    def test_fridge_query(self):
        result = check_scope("my fridge is leaking")
        assert result["in_scope"] is True

    def test_dishwasher_query(self):
        result = check_scope("dishwasher spray arm replacement")
        assert result["in_scope"] is True

    def test_part_number(self):
        result = check_scope("PS3406971")
        assert result["in_scope"] is True

    def test_part_number_in_sentence(self):
        result = check_scope("do you have PS3406971 in stock?")
        assert result["in_scope"] is True

    def test_brand_query(self):
        result = check_scope("Whirlpool parts")
        assert result["in_scope"] is True

    def test_symptom_query(self):
        result = check_scope("my dishwasher is not draining")
        assert result["in_scope"] is True

    def test_repair_query(self):
        result = check_scope("how do I replace the door gasket?")
        assert result["in_scope"] is True

    def test_compatibility_query(self):
        result = check_scope("is this part compatible with my model?")
        assert result["in_scope"] is True

    def test_shopping_query(self):
        result = check_scope("how much does the door shelf cost?")
        assert result["in_scope"] is True

    def test_help_request(self):
        result = check_scope("can you help me")
        assert result["in_scope"] is True

    def test_what_do_you_sell(self):
        result = check_scope("what do you sell")
        assert result["in_scope"] is True


# ---------------------------------------------------------------------------
# check_scope: Short/Greeting Messages (should pass through)
# ---------------------------------------------------------------------------

class TestCheckScopeGreetings:
    """Short messages with no appliance context should pass through."""

    def test_hi(self):
        assert check_scope("hi")["in_scope"] is True

    def test_hello(self):
        assert check_scope("hello")["in_scope"] is True

    def test_thanks(self):
        assert check_scope("thanks")["in_scope"] is True

    def test_yes(self):
        assert check_scope("yes please")["in_scope"] is True

    def test_empty(self):
        assert check_scope("")["in_scope"] is True

    def test_whitespace(self):
        assert check_scope("   ")["in_scope"] is True


# ---------------------------------------------------------------------------
# check_scope: Out-of-Scope Appliances
# ---------------------------------------------------------------------------

class TestCheckScopeWrongAppliance:
    """Queries about unsupported appliances should be rejected."""

    def test_washing_machine(self):
        result = check_scope("washing machine belt")
        assert result["in_scope"] is False
        assert result["detected"] == "washing machine"

    def test_dryer(self):
        result = check_scope("my dryer won't heat")
        assert result["in_scope"] is False
        assert result["detected"] == "dryer"

    def test_oven(self):
        result = check_scope("how do I fix my oven")
        assert result["in_scope"] is False
        assert result["detected"] == "oven"

    def test_microwave(self):
        result = check_scope("microwave turntable replacement")
        assert result["in_scope"] is False
        assert result["detected"] == "microwave"

    def test_stove(self):
        result = check_scope("stove burner not working")
        assert result["in_scope"] is False
        assert result["detected"] == "stove"

    def test_air_conditioner(self):
        result = check_scope("air conditioner filter")
        assert result["in_scope"] is False
        assert result["detected"] == "air conditioner"

    def test_furnace(self):
        result = check_scope("furnace ignitor replacement")
        assert result["in_scope"] is False
        assert result["detected"] == "furnace"

    def test_garbage_disposal(self):
        result = check_scope("garbage disposal jammed")
        assert result["in_scope"] is False
        assert result["detected"] == "garbage disposal"

    def test_reason_mentions_appliance(self):
        """The rejection reason should name the specific appliance."""
        result = check_scope("oven heating element")
        assert "oven" in result["reason"]

    def test_dishwasher_not_rejected_for_washer(self):
        """'dishwasher' contains 'washer' but should NOT be rejected."""
        result = check_scope("dishwasher door latch")
        assert result["in_scope"] is True

    def test_dishwasher_washer_combo(self):
        """Message with both 'dishwasher' and 'washer' should stay in scope."""
        result = check_scope("dishwasher washer arm")
        assert result["in_scope"] is True


# ---------------------------------------------------------------------------
# check_scope: Off-Topic Keywords
# ---------------------------------------------------------------------------

class TestCheckScopeOffTopic:
    """Clearly off-topic messages should be rejected."""

    def test_joke(self):
        result = check_scope("tell me a joke")
        assert result["in_scope"] is False
        assert result["detected"] == "joke"

    def test_weather(self):
        result = check_scope("what is the weather today")
        assert result["in_scope"] is False
        assert result["detected"] == "weather"

    def test_programming(self):
        result = check_scope("write me python code")
        assert result["in_scope"] is False

    def test_crypto(self):
        result = check_scope("should I invest in bitcoin")
        assert result["in_scope"] is False

    def test_recipe(self):
        result = check_scope("give me a recipe for pasta")
        assert result["in_scope"] is False

    def test_sports(self):
        result = check_scope("who won the super bowl")
        assert result["in_scope"] is False


# ---------------------------------------------------------------------------
# check_scope: No Appliance Context Heuristic
# ---------------------------------------------------------------------------

class TestCheckScopeNoContext:
    """Messages with 4+ words and zero appliance relevance should be rejected."""

    def test_dinosaurs(self):
        result = check_scope("tell me about dinosaurs")
        assert result["in_scope"] is False
        assert result["detected"] == "no_appliance_context"

    def test_meaning_of_life(self):
        result = check_scope("what is the meaning of life")
        assert result["in_scope"] is False

    def test_eiffel_tower(self):
        result = check_scope("how tall is the eiffel tower really")
        assert result["in_scope"] is False

    def test_taylor_swift(self):
        result = check_scope("who is taylor swift")
        assert result["in_scope"] is False

    def test_quantum_physics(self):
        result = check_scope("explain quantum physics to me")
        assert result["in_scope"] is False

    def test_world_war(self):
        result = check_scope("what happened in world war 2")
        assert result["in_scope"] is False


# ---------------------------------------------------------------------------
# check_scope: Edge Cases
# ---------------------------------------------------------------------------

class TestCheckScopeEdgeCases:

    def test_case_insensitive(self):
        result = check_scope("WASHING MACHINE BELT")
        assert result["in_scope"] is False

    def test_mixed_case(self):
        result = check_scope("My Dishwasher Is Leaking")
        assert result["in_scope"] is True

    def test_result_shape(self):
        """Every call returns the same dict shape."""
        result = check_scope("anything")
        assert "in_scope" in result
        assert "reason" in result
        assert "detected" in result

    def test_in_scope_has_empty_reason(self):
        result = check_scope("refrigerator filter")
        assert result["reason"] == ""
        assert result["detected"] is None

    def test_out_of_scope_has_reason(self):
        result = check_scope("oven element")
        assert result["reason"] != ""
        assert result["detected"] is not None


# ---------------------------------------------------------------------------
# validate_response: Clean Responses (no issues)
# ---------------------------------------------------------------------------

class TestValidateResponseClean:
    """Responses that should pass validation."""

    def test_empty_response(self):
        result = validate_response("")
        assert result["valid"] is True
        assert result["issues"] == []

    def test_no_part_numbers(self):
        result = validate_response("I can help you find a water filter for your fridge!")
        assert result["valid"] is True

    def test_real_part_number(self):
        """A real PS number from our database should pass."""
        result = validate_response("I found PS3406971 — it's a dishwasher wheel.")
        assert result["valid"] is True
        assert result["hallucinated_parts"] == []

    def test_multiple_real_parts(self):
        result = validate_response(
            "You might need PS3406971 or PS11701542 for your repair."
        )
        assert result["valid"] is True

    def test_correct_price_part_first(self):
        """PS number followed by correct price should pass."""
        result = validate_response("PS3406971 costs $32.91 and is in stock.")
        assert result["valid"] is True
        assert result["price_mismatches"] == []

    def test_whitespace_only(self):
        result = validate_response("   ")
        assert result["valid"] is True


# ---------------------------------------------------------------------------
# validate_response: Hallucinated Part Numbers
# ---------------------------------------------------------------------------

class TestValidateResponseHallucinatedParts:
    """Responses with fake part numbers should be flagged."""

    def test_fake_part_number(self):
        result = validate_response("Try PS9999999 — it should fix the issue.")
        assert result["valid"] is False
        assert "PS9999999" in result["hallucinated_parts"]

    def test_multiple_fake_parts(self):
        result = validate_response("Check PS9999999 and PS8888888 for options.")
        assert result["valid"] is False
        assert len(result["hallucinated_parts"]) == 2

    def test_mix_real_and_fake(self):
        """One real + one fake — only the fake should be flagged."""
        result = validate_response(
            "PS3406971 is great, but PS9999999 might also work."
        )
        assert result["valid"] is False
        assert "PS9999999" in result["hallucinated_parts"]
        assert "PS3406971" not in result["hallucinated_parts"]

    def test_issue_message_names_part(self):
        """The issue description should mention the specific part number."""
        result = validate_response("Try PS9999999.")
        assert any("PS9999999" in issue for issue in result["issues"])


# ---------------------------------------------------------------------------
# validate_response: Price Mismatches
# ---------------------------------------------------------------------------

class TestValidateResponsePriceMismatch:
    """Responses with wrong prices should be flagged."""

    def test_wrong_price(self):
        """PS3406971 is $32.91 — stating $99.99 should fail."""
        result = validate_response("PS3406971 is available for $99.99.")
        assert result["valid"] is False
        assert "PS3406971" in result["price_mismatches"]

    def test_correct_price_passes(self):
        """PS3406971 at its real price should pass."""
        result = validate_response("PS3406971 is available for $32.91.")
        assert result["valid"] is True
        assert result["price_mismatches"] == []

    def test_price_mismatch_issue_message(self):
        """Issue message should show both stated and actual price."""
        result = validate_response("PS3406971 costs $99.99 today.")
        issues_text = " ".join(result["issues"])
        assert "99.99" in issues_text
        assert "32.91" in issues_text

    def test_tiny_rounding_ok(self):
        """Price within $0.01 tolerance should pass."""
        result = validate_response("PS3406971 is $32.92 after rounding.")
        assert result["valid"] is True


# ---------------------------------------------------------------------------
# validate_response: Result Shape
# ---------------------------------------------------------------------------

class TestValidateResponseShape:
    """Every call should return the same dict shape."""

    def test_result_keys(self):
        result = validate_response("anything")
        assert "valid" in result
        assert "issues" in result
        assert "hallucinated_parts" in result
        assert "price_mismatches" in result

    def test_valid_is_bool(self):
        result = validate_response("anything")
        assert isinstance(result["valid"], bool)

    def test_issues_is_list(self):
        result = validate_response("anything")
        assert isinstance(result["issues"], list)
