"""
Tests for backend/main.py — FastAPI endpoints.

Uses FastAPI's TestClient, which calls endpoints in-process
without starting a real server.

Run:  source venv/bin/activate && python -m pytest backend/tests/test_main.py -v
"""

import pytest
from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------

class TestHealthEndpoint:

    def test_health_returns_200(self):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_ok(self):
        response = client.get("/health")
        assert response.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# POST /api/chat — request validation
# ---------------------------------------------------------------------------

class TestChatRequestValidation:

    def test_missing_body_returns_422(self):
        """No JSON body should return 422 Unprocessable Entity."""
        response = client.post("/api/chat")
        assert response.status_code == 422

    def test_empty_object_returns_422(self):
        """Empty JSON object (missing required 'message') should return 422."""
        response = client.post("/api/chat", json={})
        assert response.status_code == 422

    def test_valid_message_returns_200(self):
        """A valid message should return 200."""
        response = client.post("/api/chat", json={"message": "hi"})
        assert response.status_code == 200


# ---------------------------------------------------------------------------
# POST /api/chat — scope blocking (no API cost)
# ---------------------------------------------------------------------------

class TestChatScopeBlocking:

    def test_off_topic_blocked(self):
        response = client.post("/api/chat", json={"message": "tell me a joke"})
        assert response.status_code == 200
        data = response.json()
        assert data["products"] == []
        assert data["tool_calls"] == []
        assert "appliance" in data["message"].lower()

    def test_wrong_appliance_blocked(self):
        response = client.post("/api/chat", json={"message": "my oven is broken"})
        assert response.status_code == 200
        data = response.json()
        assert data["products"] == []
        assert data["tool_calls"] == []
        assert "oven" in data["message"].lower()


# ---------------------------------------------------------------------------
# POST /api/chat — response shape
# ---------------------------------------------------------------------------

class TestChatResponseShape:

    def test_response_has_required_fields(self):
        """Every response should have message, products, tool_calls."""
        response = client.post("/api/chat", json={"message": "hi"})
        data = response.json()
        assert "message" in data
        assert "products" in data
        assert "tool_calls" in data
        assert "conversation_id" in data

    def test_response_content_type_is_json(self):
        response = client.post("/api/chat", json={"message": "hi"})
        assert response.headers["content-type"] == "application/json"


# ---------------------------------------------------------------------------
# POST /api/chat — live tool calling
# ---------------------------------------------------------------------------

class TestChatToolCalling:

    def test_part_search_returns_products(self):
        """Searching for a known part should return products."""
        response = client.post("/api/chat", json={"message": "Do you have part PS3406971?"})
        assert response.status_code == 200
        data = response.json()
        assert len(data["products"]) >= 1
        assert any(p["part_number"] == "PS3406971" for p in data["products"])
        assert len(data["tool_calls"]) >= 1

    def test_conversation_id_passed_through(self):
        """conversation_id from request should appear in response."""
        response = client.post("/api/chat", json={
            "message": "hi",
            "conversation_id": "test-123",
        })
        data = response.json()
        assert data["conversation_id"] == "test-123"

    def test_history_accepted(self):
        """Request with history should work without error."""
        response = client.post("/api/chat", json={
            "message": "Is it compatible with model 2213223N414?",
            "history": [
                {"role": "user", "content": "I need part PS3406971"},
                {"role": "assistant", "content": "PS3406971 is a dishwasher wheel."},
            ],
        })
        assert response.status_code == 200
        data = response.json()
        assert len(data["tool_calls"]) >= 1


# ---------------------------------------------------------------------------
# Non-existent routes
# ---------------------------------------------------------------------------

class TestNotFound:

    def test_unknown_route_returns_404(self):
        response = client.get("/api/nonexistent")
        assert response.status_code == 404
