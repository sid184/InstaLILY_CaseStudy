"""
Tests for backend/models.py

Run:  source venv/bin/activate && python -m pytest backend/tests/test_models.py -v
"""

import json
import pytest
from pathlib import Path
from pydantic import ValidationError

from backend.models import (
    Installation,
    Product,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ToolCall,
)

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


# ---------------------------------------------------------------------------
# Installation
# ---------------------------------------------------------------------------

class TestInstallation:

    def test_full(self):
        inst = Installation(difficulty="Easy", time="15 mins", tools="Screwdriver")
        assert inst.difficulty == "Easy"
        assert inst.time == "15 mins"
        assert inst.tools == "Screwdriver"

    def test_partial(self):
        inst = Installation(difficulty="Hard")
        assert inst.difficulty == "Hard"
        assert inst.time is None
        assert inst.tools is None

    def test_empty(self):
        inst = Installation()
        assert inst.difficulty is None


# ---------------------------------------------------------------------------
# Product
# ---------------------------------------------------------------------------

class TestProduct:

    def test_minimal_product(self):
        p = Product(
            part_number="PS123",
            title="Test Part",
            price=9.99,
            brand="Whirlpool",
            appliance_type="dishwasher",
            url="https://www.partselect.com/PS123.htm",
        )
        assert p.part_number == "PS123"
        assert p.price == 9.99
        assert p.symptoms == []
        assert p.compatible_models == []
        assert p.in_stock is True
        assert p.installation is None

    def test_product_with_installation(self):
        p = Product(
            part_number="PS456",
            title="Filter",
            price=19.99,
            brand="GE",
            appliance_type="refrigerator",
            url="https://www.partselect.com/PS456.htm",
            installation={"difficulty": "Easy", "time": "30 mins"},
        )
        assert isinstance(p.installation, Installation)
        assert p.installation.difficulty == "Easy"

    def test_bad_price_rejected(self):
        with pytest.raises(ValidationError):
            Product(
                part_number="PS999",
                title="Bad",
                price="not_a_number",
                brand="X",
                appliance_type="dishwasher",
                url="http://x.com",
            )

    def test_missing_required_field_rejected(self):
        with pytest.raises(ValidationError):
            Product(part_number="PS999", title="No price")

    def test_load_all_products_from_json(self):
        """Every product in products.json must load without errors."""
        products_path = DATA_DIR / "products.json"
        assert products_path.exists(), f"Missing {products_path}"

        with open(products_path) as f:
            products_data = json.load(f)

        assert len(products_data) > 0, "products.json is empty"

        errors = []
        for pn, raw in products_data.items():
            try:
                Product(**raw)
            except Exception as e:
                errors.append(f"{pn}: {e}")

        assert errors == [], f"Failed to load products:\n" + "\n".join(errors)

    def test_product_fields_match_json(self):
        """Spot-check that Product fields map correctly to JSON data."""
        with open(DATA_DIR / "products.json") as f:
            products_data = json.load(f)

        raw = list(products_data.values())[0]
        product = Product(**raw)

        assert product.part_number == raw["part_number"]
        assert product.title == raw["title"]
        assert product.price == raw["price"]
        assert product.brand == raw["brand"]
        assert product.appliance_type == raw["appliance_type"]
        assert product.url == raw["url"]


# ---------------------------------------------------------------------------
# ChatMessage
# ---------------------------------------------------------------------------

class TestChatMessage:

    def test_valid(self):
        msg = ChatMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_missing_role_rejected(self):
        with pytest.raises(ValidationError):
            ChatMessage(content="No role")


# ---------------------------------------------------------------------------
# ChatRequest
# ---------------------------------------------------------------------------

class TestChatRequest:

    def test_simple(self):
        req = ChatRequest(message="Find me a water filter")
        assert req.message == "Find me a water filter"
        assert req.history == []
        assert req.conversation_id is None

    def test_with_history(self):
        req = ChatRequest(
            message="What about Whirlpool?",
            conversation_id="session-1",
            history=[
                ChatMessage(role="user", content="Find me a water filter"),
                ChatMessage(role="assistant", content="I found several..."),
            ],
        )
        assert len(req.history) == 2
        assert req.conversation_id == "session-1"

    def test_missing_message_rejected(self):
        with pytest.raises(ValidationError):
            ChatRequest()


# ---------------------------------------------------------------------------
# ToolCall
# ---------------------------------------------------------------------------

class TestToolCall:

    def test_basic(self):
        tc = ToolCall(tool="search_products", args={"query": "ice maker"})
        assert tc.tool == "search_products"
        assert tc.args == {"query": "ice maker"}
        assert tc.result_summary is None

    def test_with_summary(self):
        tc = ToolCall(
            tool="check_compatibility",
            args={"part_number": "PS123", "model_number": "WDT750"},
            result_summary="Compatible",
        )
        assert tc.result_summary == "Compatible"


# ---------------------------------------------------------------------------
# ChatResponse
# ---------------------------------------------------------------------------

class TestChatResponse:

    def test_text_only(self):
        resp = ChatResponse(message="Hello, how can I help?")
        assert resp.message == "Hello, how can I help?"
        assert resp.products == []
        assert resp.tool_calls == []

    def test_with_products_and_tools(self):
        product = Product(
            part_number="PS3406971",
            title="Lower Dishrack Wheel",
            price=7.60,
            brand="Whirlpool",
            appliance_type="dishwasher",
            url="https://www.partselect.com/PS3406971.htm",
        )
        resp = ChatResponse(
            message="I found a matching part.",
            products=[product],
            tool_calls=[
                ToolCall(tool="search_products", args={"query": "dishrack wheel"}),
            ],
            conversation_id="session-1",
        )
        assert len(resp.products) == 1
        assert resp.products[0].part_number == "PS3406971"
        assert len(resp.tool_calls) == 1

    def test_json_round_trip(self):
        """Serialize to JSON and back — this is what FastAPI does."""
        resp = ChatResponse(
            message="Test response",
            products=[
                Product(
                    part_number="PS100",
                    title="Test",
                    price=10.0,
                    brand="LG",
                    appliance_type="refrigerator",
                    url="https://example.com",
                )
            ],
            tool_calls=[ToolCall(tool="search_products", args={})],
        )
        json_str = resp.model_dump_json()
        parsed = ChatResponse.model_validate_json(json_str)
        assert parsed.message == resp.message
        assert len(parsed.products) == 1
        assert parsed.products[0].part_number == "PS100"
        assert len(parsed.tool_calls) == 1
