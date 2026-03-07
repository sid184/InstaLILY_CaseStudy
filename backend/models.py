"""
Pydantic data models for the PartSelect chat agent.

These models serve as the contract between:
  - Our JSON data files and the backend (Product, Installation)
  - The frontend and the API (ChatRequest, ChatResponse)
  - The agent and its tool outputs (ToolCall)
"""

from pydantic import BaseModel, Field
from typing import List, Literal, Optional


# ---------------------------------------------------------------------------
# Data Models (match the shape of data/products.json)
# ---------------------------------------------------------------------------

class Installation(BaseModel):
    """Installation details for a part."""
    difficulty: Optional[str] = None       # e.g. "Really Easy", "Easy"
    time: Optional[str] = None             # e.g. "Less than 15 mins"
    tools: Optional[str] = None            # e.g. "Screw drivers, Wrench"
    repair_story_title: Optional[str] = None   # Title of top customer repair story
    repair_story_text: Optional[str] = None    # First paragraph of that story


class Product(BaseModel):
    """A single appliance part from our product database."""
    part_number: str                                    # e.g. "PS3406971"
    title: str                                          # e.g. "Lower Dishrack Wheel W10195416"
    price: float                                        # e.g. 7.60
    brand: str                                          # e.g. "Whirlpool"
    appliance_type: str                                 # "refrigerator" or "dishwasher"
    url: str                                            # Full PartSelect URL
    image_url: Optional[str] = None                     # CDN image URL
    description: Optional[str] = None
    rating: Optional[float] = None                      # 0.0 - 5.0
    review_count: Optional[int] = None
    in_stock: bool = True
    symptoms: List[str] = Field(default_factory=list)   # e.g. ["Leaking", "Won't start"]
    compatible_models: List[str] = Field(default_factory=list)
    manufacturer_part_number: Optional[str] = None
    installation: Optional[Installation] = None


# ---------------------------------------------------------------------------
# API Request / Response Models
# ---------------------------------------------------------------------------

class ChatMessage(BaseModel):
    """A single message in the conversation history."""
    role: str       # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    """What the frontend sends to POST /api/chat."""
    message: str
    conversation_id: Optional[str] = None
    history: List[ChatMessage] = Field(default_factory=list)


class ToolCall(BaseModel):
    """Record of a tool the agent decided to use."""
    tool: str                       # e.g. "search_products", "check_compatibility"
    args: dict = Field(default_factory=dict)
    result_summary: Optional[str] = None   # Brief human-readable result


class ChatResponse(BaseModel):
    """What POST /api/chat returns to the frontend."""
    message: str                                        # The agent's text reply
    products: List[Product] = Field(default_factory=list)  # Product cards to display
    tool_calls: List[ToolCall] = Field(default_factory=list)  # Tools the agent used
    conversation_id: Optional[str] = None
    installation_result: Optional[dict] = None         # Result of get_installation_guide
    compatibility_result: Optional[dict] = None        # Result of check_compatibility
    diagnostic_result: Optional[dict] = None           # Result of diagnose_problem
    response_type: Literal["general", "installation", "compatibility", "diagnostic"] = "general"
    suggested_prompts: List[str] = Field(default_factory=list)
