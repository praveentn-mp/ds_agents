"""Orchestrator nodes — intent classification, capability resolution, routing."""

import json
from sqlalchemy import select
from backend.agents.state import ADFAgentState
from backend.agents.llm import invoke_llm, get_model_name
from backend.database import async_session
from backend.models.connector import Connector


async def classify_intent(state: ADFAgentState) -> dict:
    """Classify user intent into: query, tool, hybrid, rag, build_connector, build_tool."""
    user_message = state["messages"][-1]["content"]

    prompt = f"""Classify the following user request into exactly one intent category.

Categories:
- query: The user wants to query/analyze data from a database or data source
- tool: The user wants to use an external tool or automation
- rag: The user wants to search/retrieve information from documents
- hybrid: The user needs both data querying AND tool usage
- build_connector: The user wants to create a new data connector
- build_tool: The user wants to create a new custom tool

User request: "{user_message}"

Respond with ONLY a JSON object: {{"intent": "<category>", "reasoning": "<brief explanation>"}}"""

    try:
        content, usage = await invoke_llm(prompt)
        content = content.strip()
        if "```" in content:
            content = content.split("```")[1].strip()
            if content.startswith("json"):
                content = content[4:].strip()
        parsed = json.loads(content)
        intent = parsed.get("intent", "query")
    except Exception:
        intent = "query"
        usage = None

    result = {
        "intent": intent,
        "current_step": 1,
        "trace_events": [{
            "type": "intent_classification",
            "agent": "orchestrator",
            "status": "success",
            "payload": {"intent": intent, "message": user_message},
            "sequence": 1,
        }],
    }

    if usage:
        token_count = state.get("token_count", {"input": 0, "output": 0, "cache": 0})
        result["token_count"] = {
            "input": token_count["input"] + usage.tokens_input,
            "output": token_count["output"] + usage.tokens_output,
            "cache": token_count["cache"] + usage.tokens_cache,
        }
        result["llm_calls"] = [{"model": usage.model, "tokens_input": usage.tokens_input,
                                 "tokens_output": usage.tokens_output, "tokens_cache": usage.tokens_cache,
                                 "latency_ms": usage.latency_ms, "node": "classify_intent"}]

    return result


async def resolve_capabilities(state: ADFAgentState) -> dict:
    """Resolve available capabilities from the database."""
    capabilities = []

    try:
        async with async_session() as db:
            result = await db.execute(
                select(Connector).where(Connector.is_active == True)
            )
            connectors = result.scalars().all()
            for c in connectors:
                capabilities.append({
                    "type": "connector",
                    "name": c.name,
                    "connector_type": c.connector_type,
                    "description": c.description or f"{c.connector_type} connector",
                })
    except Exception:
        pass

    # Always include built-in tool capabilities
    capabilities.extend([
        {"type": "tool", "name": "QueryResource", "description": "Query any connector resource"},
        {"type": "tool", "name": "WriteResource", "description": "Write to any connector resource"},
        {"type": "tool", "name": "MCPToolCall", "description": "Call any MCP server tool"},
    ])

    return {
        "capabilities": capabilities,
        "route": state.get("intent", "query"),
        "current_step": 2,
        "trace_events": [{
            "type": "capability_resolution",
            "agent": "orchestrator",
            "status": "success",
            "payload": {"capabilities_count": len(capabilities)},
            "sequence": 2,
        }],
    }


def route_decision(state: ADFAgentState) -> str:
    """Route to the appropriate agent based on intent."""
    intent = state.get("intent", "query")
    mapping = {
        "query": "query",
        "tool": "tool",
        "rag": "rag",
        "hybrid": "hybrid",
        "build_connector": "tool",
        "build_tool": "tool",
    }
    return mapping.get(intent, "query")
