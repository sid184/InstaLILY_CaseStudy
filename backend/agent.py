"""
Chat agent for PartSelect — orchestrates Claude, tools, and safety checks.

Flow:
  1. User message comes in
  2. check_scope() gates off-topic queries
  3. Claude decides which tools to call (if any)
  4. Tool results feed back into Claude for a final answer
  5. validate_response() catches hallucinated data before we reply
"""

import json
import os
import re
from pathlib import Path
from typing import List, Optional

import anthropic
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from backend.models import ChatRequest, ChatResponse, Product, ToolCall
from backend.safety import check_scope, validate_response
from backend.tools import (
    search_products,
    check_compatibility,
    get_installation_guide,
    diagnose_problem,
    get_related_parts,
)


# ---------------------------------------------------------------------------
# System Prompt
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are a helpful customer service assistant for PartSelect, an online retailer specialising in refrigerator and dishwasher replacement parts.

YOUR ROLE:
- Help customers find the right parts for their refrigerator or dishwasher
- Check if parts are compatible with their appliance model
- Provide installation guidance and difficulty estimates
- Diagnose problems based on symptoms and suggest parts that fix them
- Suggest related parts the customer might also need

RULES YOU MUST FOLLOW:
1. ONLY discuss refrigerator and dishwasher parts. If asked about other appliances (ovens, washing machines, dryers, etc.), politely explain you only cover refrigerators and dishwashers and suggest they visit PartSelect.com for other categories.
2. NEVER invent part numbers. Only reference parts returned by your tools. If you don't find a match, say so honestly.
3. NEVER guess prices. Only state prices returned by your tools. If a tool didn't return a price, don't make one up.
4. ALWAYS use your tools to look up information. Do not rely on your training data for part numbers, prices, compatibility, or installation details.
5. When a customer describes a symptom, use the diagnose_problem tool before suggesting parts.
6. When a customer asks about compatibility, you MUST call check_compatibility FIRST before saying anything about whether a part fits a model. NEVER state compatibility verdicts from your own training knowledge — the tool result is the ONLY source of truth. If the tool returns model_found: false, tell the customer that model is not in our database and provide a PartSelect search link: https://www.partselect.com/search/?searchterm=MODELNUMBER
7. Include the PartSelect URL when recommending a specific part so the customer can view it.
8. Be concise and helpful. Customers want answers, not essays.
9. If you're unsure, say so. It's better to say "I couldn't find that" than to guess.
10. When you call get_installation_guide, do NOT repeat the difficulty, time, or tools in your text response — the UI displays a dedicated Installation Guide card with that data. Instead, write one short sentence summarising the task (e.g. "This is a quick, tool-free swap.") and invite the customer to check the card or visit the PartSelect page for the full step-by-step video guide.
11. When search_products returns no results for a specific part number (e.g. PS99999999 or W10295370A), tell the customer that part is not in our local database and provide a direct PartSelect search link: https://www.partselect.com/search/?searchterm=PARTNUMBER — replace PARTNUMBER with the actual part number they asked about.

TONE:
- Friendly and professional
- Use plain language, not jargon
- Be direct — customers are here to solve a problem
"""


# ---------------------------------------------------------------------------
# Tool Definitions (Anthropic tool-use schema)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = [
    {
        "name": "search_products",
        "description": (
            "Search for appliance parts by part number, keyword, or natural language. "
            "Use this when the customer asks about a specific part, searches by name, "
            "or mentions a manufacturer part number."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "The search query — a PS part number (e.g. 'PS3406971'), "
                        "a manufacturer part number (e.g. 'W10195416'), "
                        "or a keyword/phrase (e.g. 'water filter', 'door shelf bin')."
                    ),
                },
                "appliance_type": {
                    "type": "string",
                    "enum": ["refrigerator", "dishwasher"],
                    "description": "Optional filter to only return parts for this appliance type.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "check_compatibility",
        "description": (
            "Check whether a specific part fits a specific appliance model. "
            "Use this when the customer asks 'does part X fit model Y?' or "
            "'is this compatible with my model?'. Returns alternatives if incompatible."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "part_number": {
                    "type": "string",
                    "description": "The PartSelect part number (e.g. 'PS3406971').",
                },
                "model_number": {
                    "type": "string",
                    "description": "The appliance model number (e.g. '2213223N414').",
                },
            },
            "required": ["part_number", "model_number"],
        },
    },
    {
        "name": "get_installation_guide",
        "description": (
            "Get installation details for a specific part, including difficulty level, "
            "estimated time, and tools needed. Use this when the customer asks "
            "'how do I install this?' or 'is this hard to replace?'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "part_number": {
                    "type": "string",
                    "description": "The PartSelect part number (e.g. 'PS3406971').",
                },
            },
            "required": ["part_number"],
        },
    },
    {
        "name": "diagnose_problem",
        "description": (
            "Given a symptom or problem description, find parts that are known to fix it. "
            "Use this when the customer describes a problem like 'my dishwasher is leaking' "
            "or 'ice maker not working'. Always use this BEFORE suggesting parts for a symptom."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "symptom": {
                    "type": "string",
                    "description": (
                        "The problem or symptom description "
                        "(e.g. 'leaking', 'not draining', 'ice maker not working')."
                    ),
                },
                "appliance_type": {
                    "type": "string",
                    "enum": ["refrigerator", "dishwasher"],
                    "description": "Optional filter — the type of appliance with the problem.",
                },
            },
            "required": ["symptom"],
        },
    },
    {
        "name": "get_related_parts",
        "description": (
            "Find parts related to a given part — other parts that fit the same appliance "
            "models. Use this when the customer says 'what else might I need?' or "
            "after recommending a part to suggest complementary items."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "part_number": {
                    "type": "string",
                    "description": "The PartSelect part number to find related parts for.",
                },
            },
            "required": ["part_number"],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool Dispatcher
# ---------------------------------------------------------------------------

# Map tool names to their Python functions
_TOOL_FUNCTIONS = {
    "search_products": search_products,
    "check_compatibility": check_compatibility,
    "get_installation_guide": get_installation_guide,
    "diagnose_problem": diagnose_problem,
    "get_related_parts": get_related_parts,
}


def _execute_tool(tool_name: str, tool_input: dict) -> str:
    """
    Execute a tool by name with the given arguments, return a JSON string.

    This is the bridge between Claude's tool call (a name + dict of args)
    and our actual Python functions. It:
      1. Looks up the function by name
      2. Calls it with the provided arguments
      3. Serialises the result to JSON (handling Pydantic models and lists)

    Args:
        tool_name: The tool name from Claude's response (e.g. "search_products")
        tool_input: The arguments dict from Claude (e.g. {"query": "water filter"})

    Returns:
        A JSON string of the tool's result, ready to send back to Claude.
    """
    func = _TOOL_FUNCTIONS.get(tool_name)
    if func is None:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    try:
        result = func(**tool_input)
    except Exception as e:
        return json.dumps({"error": f"Tool '{tool_name}' failed: {str(e)}"})

    return _serialise_result(result)


def _serialise_result(obj) -> str:
    """
    Convert a tool result to a JSON string Claude can read.

    Handles:
      - Pydantic models (via .model_dump())
      - Lists of Pydantic models
      - Dicts containing Pydantic models or lists of them
      - Plain dicts, strings, numbers
    """
    if hasattr(obj, "model_dump"):
        return json.dumps(obj.model_dump(), default=str)

    if isinstance(obj, list):
        return json.dumps(
            [item.model_dump() if hasattr(item, "model_dump") else item for item in obj],
            default=str,
        )

    if isinstance(obj, dict):
        cleaned = {}
        for key, value in obj.items():
            if hasattr(value, "model_dump"):
                cleaned[key] = value.model_dump()
            elif isinstance(value, list):
                cleaned[key] = [
                    item.model_dump() if hasattr(item, "model_dump") else item
                    for item in value
                ]
            else:
                cleaned[key] = value
        return json.dumps(cleaned, default=str)

    return json.dumps(obj, default=str)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODEL_SONNET = "claude-sonnet-4-20250514"
MODEL_HAIKU = "claude-haiku-4-5-20251001"
MAX_TOOL_ROUNDS = 10  # Safety cap — prevent infinite tool-calling loops

_TOOL_SIGNALS = re.compile(
    r'PS\d{5,}'                                               # part number: PS11701542
    r'|\b[A-Z]{2,}\d{3,}[A-Z0-9]*\b'                        # model number: WDT750SAHZ0
    r'|fit|compatible|work with'                              # compatibility
    r'|install|replace|fix|repair'                            # installation/repair
    r'|not\s+(working|draining|cooling|heating|spinning|making ice)'  # symptoms
    r'|symptom|problem|issue|broken|leaking|noisy'            # more symptoms
    r'|part|model|refrigerator|fridge|dishwasher',            # product domain
    re.IGNORECASE,
)

def select_model(message: str) -> str:
    """Route to Haiku for purely conversational messages, Sonnet for anything tool-related."""
    return MODEL_SONNET if _TOOL_SIGNALS.search(message) else MODEL_HAIKU


# ---------------------------------------------------------------------------
# process_chat — the main agent loop
# ---------------------------------------------------------------------------

def process_chat(request: ChatRequest) -> ChatResponse:
    """
    Process a user chat message and return the agent's response.

    This is the main entry point — called by the FastAPI endpoint.

    Flow:
      1. Run check_scope() to reject off-topic messages early
      2. Build the Anthropic messages list from conversation history
      3. Send to Claude with our tools available
      4. If Claude wants to call tools, execute them and loop back
      5. Once Claude produces a final text response, run validate_response()
      6. Collect any Product objects from tool results for the frontend
      7. Return a ChatResponse

    Args:
        request: The incoming ChatRequest from the frontend.

    Returns:
        A ChatResponse with the agent's message, products, and tool call log.
    """
    # --- Step 1: Scope check ---
    scope = check_scope(request.message, has_history=bool(request.history))
    if not scope["in_scope"]:
        return ChatResponse(
            message=scope["reason"],
            conversation_id=request.conversation_id,
        )

    # --- Step 2: Build messages list ---
    messages = []

    # Add conversation history (previous turns)
    for msg in request.history:
        messages.append({"role": msg.role, "content": msg.content})

    # Add the current user message
    messages.append({"role": "user", "content": request.message})

    # --- Step 3: Create the Anthropic client ---
    client = anthropic.Anthropic()  # Uses ANTHROPIC_API_KEY env var

    # Track tool calls and products for the response
    tool_call_log: List[ToolCall] = []
    collected_products: List[Product] = []
    installation_result: Optional[dict] = None
    compatibility_result: Optional[dict] = None
    diagnostic_result: Optional[dict] = None
    response_type: str = "general"

    # --- Step 4: Tool-calling loop ---
    for _ in range(MAX_TOOL_ROUNDS):
        response = client.messages.create(
            model=select_model(request.message),
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOL_DEFINITIONS,
            messages=messages,
        )

        # Check if Claude wants to use tools
        if response.stop_reason == "tool_use":
            # Claude's response may contain text + tool_use blocks
            # We need to add the full assistant response, then add tool results

            # Add Claude's response (with tool_use blocks) to the conversation
            messages.append({"role": "assistant", "content": response.content})

            # Process each tool call in this response
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    # Execute the tool
                    result_json = _execute_tool(block.name, block.input)

                    # Log the tool call
                    tool_call_log.append(ToolCall(
                        tool=block.name,
                        args=block.input,
                        result_summary=result_json[:200],
                    ))

                    # Capture typed results for specialised frontend components
                    if block.name == "get_installation_guide":
                        try:
                            installation_result = json.loads(result_json)
                            response_type = "installation"
                        except Exception:
                            pass
                    elif block.name == "check_compatibility":
                        try:
                            compatibility_result = json.loads(result_json)
                            response_type = "compatibility"
                        except Exception:
                            pass
                    elif block.name == "diagnose_problem":
                        try:
                            diagnostic_result = json.loads(result_json)
                            response_type = "diagnostic"
                        except Exception:
                            pass

                    # Collect Product objects from tool results
                    _collect_products(block.name, block.input, collected_products)

                    # Build the tool_result message for Claude
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result_json,
                    })

            # Send tool results back to Claude
            messages.append({"role": "user", "content": tool_results})

        else:
            # Claude is done — extract the final text response
            break

    # --- Step 5: Extract final text ---
    final_text = ""
    for block in response.content:
        if hasattr(block, "text"):
            final_text += block.text

    # --- Step 6: Validate response ---
    validation = validate_response(final_text)
    if not validation["valid"]:
        # Append a disclaimer — don't suppress the whole response
        issues = "; ".join(validation["issues"])
        final_text += (
            f"\n\n⚠️ *Some information in this response could not be verified "
            f"against our database: {issues}*"
        )

    # --- Step 7: Generate contextual follow-up suggestions ---
    suggested_prompts = _generate_suggestions(client, request.message, final_text)

    # --- Step 8: Return ChatResponse ---
    return ChatResponse(
        message=final_text,
        products=collected_products,
        tool_calls=tool_call_log,
        conversation_id=request.conversation_id,
        installation_result=installation_result,
        compatibility_result=compatibility_result,
        diagnostic_result=diagnostic_result,
        response_type=response_type,
        suggested_prompts=suggested_prompts,
    )


def _collect_products(tool_name: str, tool_input: dict, products: List[Product]):
    """
    Re-run the tool to collect Product objects for the frontend.

    We call the tool functions again (they're fast, in-memory lookups)
    to get the actual Product models, since the serialised JSON we sent
    to Claude doesn't give us Pydantic objects back.
    """
    try:
        if tool_name == "search_products":
            results = search_products(**tool_input)
            products.extend(results)

        elif tool_name == "check_compatibility":
            result = check_compatibility(**tool_input)
            if result["part"]:
                products.append(result["part"])
            products.extend(result.get("compatible_parts", []))

        elif tool_name == "diagnose_problem":
            result = diagnose_problem(**tool_input)
            products.extend(result.get("parts", []))

        elif tool_name == "get_related_parts":
            result = get_related_parts(**tool_input)
            products.extend(result.get("related", []))

    except Exception:
        pass  # Don't let product collection break the response


def _generate_suggestions(client: anthropic.Anthropic, user_message: str, assistant_reply: str) -> List[str]:
    """Use Haiku to generate 3 contextual follow-up suggestions based on the conversation."""
    try:
        resp = client.messages.create(
            model=MODEL_HAIKU,
            max_tokens=128,
            system=(
                "You generate suggested messages that a USER would type to a refrigerator and dishwasher parts assistant. "
                "These are clickable chips shown to the user to help them continue the conversation. "
                "Write them in first person as if the user is typing them (e.g. 'My refrigerator is leaking', 'Does PS11701542 fit my model?', 'How do I install this part?'). "
                "Return exactly 3 short user messages, one per line, no numbering, no bullet points, no extra text."
            ),
            messages=[{
                "role": "user",
                "content": (
                    f"User asked: {user_message}\n"
                    f"Assistant replied: {assistant_reply[:400]}\n\n"
                    "Generate 3 short messages the user might type next."
                ),
            }],
        )
        lines = resp.content[0].text.strip().splitlines()
        suggestions = [l.lstrip("0123456789.-) ").strip() for l in lines if l.strip()]
        return suggestions[:3]
    except Exception:
        return []
