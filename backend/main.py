"""
FastAPI server for the PartSelect chat agent.

Endpoints:
  POST /api/chat  — Main chat endpoint, calls the agent
  GET  /health    — Health check

Run:
  uvicorn backend.main:app --reload
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.agent import process_chat
from backend.models import ChatRequest, ChatResponse


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="PartSelect Chat Agent",
    description="AI assistant for refrigerator and dishwasher parts",
    version="1.0.0",
)

# CORS — allow the frontend to talk to us
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",    # Next.js dev server
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
def health_check():
    """Simple health check — returns 200 if the server is running."""
    return {"status": "ok"}


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """
    Main chat endpoint.

    Accepts a user message (with optional conversation history),
    runs it through the agent, and returns the response.
    """
    return process_chat(request)
