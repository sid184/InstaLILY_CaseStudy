"""
Tests for backend/agent.py

Split into two sections:
  - Local tests (no API key needed): tool dispatcher, serialisation, product collection
  - Live API tests: full process_chat() with real Claude calls

Run:  source venv/bin/activate && python -m pytest backend/tests/test_agent.py -v
"""

import json

import pytest
from backend.agent import (
    _execute_tool,
    _serialise_result,
    _collect_products,
    process_chat,
    TOOL_DEFINITIONS,
    _TOOL_FUNCTIONS,
)
from backend.models import ChatRequest, ChatResponse, Product, ToolCall


# ===========================================================================
# LOCAL TESTS — no API calls, free, fast, deterministic
# ===========================================================================


# ---------------------------------------------------------------------------
# Tool Definitions: structural checks
# ---------------------------------------------------------------------------

class TestToolDefinitions:
    """Verify tool definitions match our actual tool functions."""

    def test_all_tools_have_definitions(self):
        """Every function in _TOOL_FUNCTIONS has a matching definition."""
        defined_names = {t["name"] for t in TOOL_DEFINITIONS}
        for name in _TOOL_FUNCTIONS:
            assert name in defined_names, f"{name} missing from TOOL_DEFINITIONS"

    def test_all_definitions_have_functions(self):
        """Every definition points to a real function."""
        for tool_def in TOOL_DEFINITIONS:
            assert tool_def["name"] in _TOOL_FUNCTIONS

    def test_definitions_have_required_fields(self):
        """Each tool definition has name, description, and input_schema."""
        for tool_def in TOOL_DEFINITIONS:
            assert "name" in tool_def
            assert "description" in tool_def
            assert "input_schema" in tool_def
            assert tool_def["input_schema"]["type"] == "object"


# ---------------------------------------------------------------------------
# _execute_tool: dispatching and serialisation
# ---------------------------------------------------------------------------

class TestExecuteTool:
    """Test the tool dispatcher with real tool functions."""

    def test_search_products_returns_json(self):
        result = _execute_tool("search_products", {"query": "PS3406971"})
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) == 1
        assert parsed[0]["part_number"] == "PS3406971"

    def test_check_compatibility_returns_json(self):
        result = _execute_tool("check_compatibility", {
            "part_number": "PS3406971",
            "model_number": "2213223N414",
        })
        parsed = json.loads(result)
        assert parsed["compatible"] is True

    def test_get_installation_guide_returns_json(self):
        result = _execute_tool("get_installation_guide", {"part_number": "PS3406971"})
        parsed = json.loads(result)
        assert parsed["found"] is True

    def test_diagnose_problem_returns_json(self):
        result = _execute_tool("diagnose_problem", {
            "symptom": "leaking",
            "appliance_type": "dishwasher",
        })
        parsed = json.loads(result)
        assert len(parsed["parts"]) > 0

    def test_get_related_parts_returns_json(self):
        result = _execute_tool("get_related_parts", {"part_number": "PS3406971"})
        parsed = json.loads(result)
        assert parsed["found"] is True
        assert len(parsed["related"]) > 0

    def test_unknown_tool_returns_error(self):
        result = _execute_tool("nonexistent_tool", {})
        parsed = json.loads(result)
        assert "error" in parsed
        assert "Unknown tool" in parsed["error"]

    def test_bad_args_returns_error(self):
        """Passing wrong arguments should return an error, not crash."""
        result = _execute_tool("search_products", {"bad_param": "value"})
        parsed = json.loads(result)
        assert "error" in parsed

    def test_result_is_valid_json(self):
        """Every tool should return parseable JSON."""
        for tool_name in _TOOL_FUNCTIONS:
            if tool_name == "search_products":
                result = _execute_tool(tool_name, {"query": "filter"})
            elif tool_name == "check_compatibility":
                result = _execute_tool(tool_name, {
                    "part_number": "PS3406971",
                    "model_number": "2213223N414",
                })
            elif tool_name == "diagnose_problem":
                result = _execute_tool(tool_name, {"symptom": "leaking"})
            else:
                result = _execute_tool(tool_name, {"part_number": "PS3406971"})

            # Should not raise
            parsed = json.loads(result)
            assert parsed is not None


# ---------------------------------------------------------------------------
# _serialise_result: Pydantic model handling
# ---------------------------------------------------------------------------

class TestSerialiseResult:
    """Test serialisation of different result types."""

    def test_pydantic_model(self):
        product = Product(
            part_number="PS1234567",
            title="Test Part",
            price=9.99,
            brand="TestBrand",
            appliance_type="dishwasher",
            url="https://example.com",
        )
        result = _serialise_result(product)
        parsed = json.loads(result)
        assert parsed["part_number"] == "PS1234567"
        assert parsed["price"] == 9.99

    def test_list_of_models(self):
        products = [
            Product(
                part_number="PS1111111",
                title="Part A",
                price=1.00,
                brand="A",
                appliance_type="dishwasher",
                url="https://a.com",
            ),
            Product(
                part_number="PS2222222",
                title="Part B",
                price=2.00,
                brand="B",
                appliance_type="refrigerator",
                url="https://b.com",
            ),
        ]
        result = _serialise_result(products)
        parsed = json.loads(result)
        assert len(parsed) == 2
        assert parsed[0]["part_number"] == "PS1111111"
        assert parsed[1]["part_number"] == "PS2222222"

    def test_dict_with_nested_model(self):
        product = Product(
            part_number="PS1234567",
            title="Test",
            price=5.00,
            brand="X",
            appliance_type="dishwasher",
            url="https://x.com",
        )
        data = {"found": True, "part": product, "count": 1}
        result = _serialise_result(data)
        parsed = json.loads(result)
        assert parsed["found"] is True
        assert parsed["part"]["part_number"] == "PS1234567"
        assert parsed["count"] == 1

    def test_dict_with_list_of_models(self):
        product = Product(
            part_number="PS1234567",
            title="Test",
            price=5.00,
            brand="X",
            appliance_type="dishwasher",
            url="https://x.com",
        )
        data = {"results": [product], "total": 1}
        result = _serialise_result(data)
        parsed = json.loads(result)
        assert len(parsed["results"]) == 1
        assert parsed["results"][0]["part_number"] == "PS1234567"

    def test_plain_dict(self):
        result = _serialise_result({"key": "value", "num": 42})
        parsed = json.loads(result)
        assert parsed["key"] == "value"
        assert parsed["num"] == 42

    def test_plain_string(self):
        result = _serialise_result("hello")
        assert json.loads(result) == "hello"


# ---------------------------------------------------------------------------
# _collect_products: product gathering from tool calls
# ---------------------------------------------------------------------------

class TestCollectProducts:
    """Test product collection for the frontend."""

    def test_search_products_collects(self):
        products = []
        _collect_products("search_products", {"query": "PS3406971"}, products)
        assert len(products) == 1
        assert products[0].part_number == "PS3406971"

    def test_check_compatibility_collects_part(self):
        products = []
        _collect_products("check_compatibility", {
            "part_number": "PS3406971",
            "model_number": "2213223N414",
        }, products)
        assert any(p.part_number == "PS3406971" for p in products)

    def test_diagnose_problem_collects(self):
        products = []
        _collect_products("diagnose_problem", {
            "symptom": "leaking",
            "appliance_type": "dishwasher",
        }, products)
        assert len(products) > 0

    def test_get_related_parts_collects(self):
        products = []
        _collect_products("get_related_parts", {"part_number": "PS3406971"}, products)
        assert len(products) > 0
        # Related parts should not include the original
        assert all(p.part_number != "PS3406971" for p in products)

    def test_installation_guide_collects_nothing(self):
        products = []
        _collect_products("get_installation_guide", {"part_number": "PS3406971"}, products)
        assert len(products) == 0

    def test_bad_tool_does_not_crash(self):
        products = []
        _collect_products("nonexistent_tool", {}, products)
        assert len(products) == 0

    def test_bad_args_does_not_crash(self):
        products = []
        _collect_products("search_products", {"bad_param": "value"}, products)
        assert len(products) == 0


# ===========================================================================
# LIVE API TESTS — require ANTHROPIC_API_KEY, cost a small amount per run
# ===========================================================================


class TestProcessChatScopeCheck:
    """Scope checking should block bad queries without calling the API."""

    def test_off_topic_blocked(self):
        request = ChatRequest(message="tell me a joke")
        response = process_chat(request)
        assert isinstance(response, ChatResponse)
        assert len(response.tool_calls) == 0
        assert len(response.products) == 0
        assert "appliance" in response.message.lower()

    def test_wrong_appliance_blocked(self):
        request = ChatRequest(message="my oven is broken")
        response = process_chat(request)
        assert isinstance(response, ChatResponse)
        assert len(response.tool_calls) == 0
        assert "oven" in response.message.lower()

    def test_greeting_passes_through(self):
        """A simple greeting should reach Claude, not be blocked."""
        request = ChatRequest(message="hi")
        response = process_chat(request)
        assert isinstance(response, ChatResponse)
        assert response.message != ""


class TestProcessChatToolCalling:
    """Test that Claude correctly uses our tools."""

    def test_part_search_uses_search_tool(self):
        """Asking about a specific part should trigger search_products."""
        request = ChatRequest(message="Do you have part PS3406971?")
        response = process_chat(request)

        assert isinstance(response, ChatResponse)
        tool_names = [tc.tool for tc in response.tool_calls]
        assert "search_products" in tool_names
        assert len(response.products) >= 1
        assert any(p.part_number == "PS3406971" for p in response.products)

    def test_compatibility_check_uses_tool(self):
        """Asking about compatibility should trigger check_compatibility."""
        request = ChatRequest(message="Does PS3406971 fit model 2213223N414?")
        response = process_chat(request)

        tool_names = [tc.tool for tc in response.tool_calls]
        assert "check_compatibility" in tool_names

    def test_symptom_uses_diagnose_tool(self):
        """Describing a symptom should trigger diagnose_problem."""
        request = ChatRequest(message="My dishwasher is leaking from the bottom")
        response = process_chat(request)

        tool_names = [tc.tool for tc in response.tool_calls]
        assert "diagnose_problem" in tool_names
        assert len(response.products) >= 1

    def test_response_has_correct_shape(self):
        """Every response should have the right ChatResponse fields."""
        request = ChatRequest(message="refrigerator water filter")
        response = process_chat(request)

        assert isinstance(response.message, str)
        assert isinstance(response.products, list)
        assert isinstance(response.tool_calls, list)
        assert all(isinstance(p, Product) for p in response.products)
        assert all(isinstance(tc, ToolCall) for tc in response.tool_calls)


class TestProcessChatConversationHistory:
    """Test that conversation history is passed through correctly."""

    def test_history_provides_context(self):
        """Claude should reference earlier context from history."""
        from backend.models import ChatMessage
        request = ChatRequest(
            message="Is it compatible with model 2213223N414?",
            history=[
                ChatMessage(role="user", content="I need part PS3406971"),
                ChatMessage(role="assistant", content="PS3406971 is a Lower Dishrack Wheel for dishwashers, priced at $32.91."),
            ],
        )
        response = process_chat(request)

        # Claude should use check_compatibility since it has the part from history
        tool_names = [tc.tool for tc in response.tool_calls]
        assert "check_compatibility" in tool_names
