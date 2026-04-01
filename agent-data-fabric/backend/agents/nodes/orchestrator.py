"""Orchestrator nodes — intent classification, capability resolution, routing."""

import json
from sqlalchemy import select
from backend.agents.state import ADFAgentState
from backend.agents.llm import invoke_llm, get_model_name
from backend.database import async_session
from backend.models.connector import Connector
from backend.models.custom_tool import CustomTool


async def classify_intent(state: ADFAgentState) -> dict:
    """Classify user intent into: query, tool, hybrid, build_connector, build_tool."""
    user_message = state["messages"][-1]["content"]

    prompt = f"""Classify the following user request into exactly one intent category.

Categories:
- query: The user wants to query, analyze, search, or retrieve data from databases — questions about companies, products, people, records, metrics, values in their data tables.
- tool: The user explicitly wants to use, run, or execute a named custom tool or automation (e.g. "run the top_wines tool", "execute list_companies_by_country")
- meta: The user is asking about the SYSTEM ITSELF — list tools, show connectors, what data is ingested, what tables exist, what tools are available, system capabilities, or any question about the platform rather than the data inside it.
- hybrid: The user needs both data querying AND tool usage in the same request
- build_connector: The user wants to create a new data connector
- build_tool: The user wants to create a new custom tool

IMPORTANT RULES:
- "get me all tools" / "what tools are available" / "list my tools" → meta
- "what data is ingested" / "show me the connectors" / "what tables do I have" → meta
- "get me the details of globex company" / "show top companies" → query
- "run the top_wines tool" / "execute list_companies_by_country" → tool
- If the user is asking about ANY DATA CONTENT (entities, records, metrics) → query
- If the user is asking about the SYSTEM or PLATFORM features → meta
- Only classify as "tool" if they explicitly reference running a specific tool by name.

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
    """Resolve available capabilities from the database — connectors + custom tools."""
    capabilities = []

    try:
        async with async_session() as db:
            # Active connectors
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

            # Active custom tools
            tool_result = await db.execute(
                select(CustomTool).where(CustomTool.is_active == True)
            )
            custom_tools = tool_result.scalars().all()
            for t in custom_tools:
                capabilities.append({
                    "type": "tool",
                    "name": t.name,
                    "description": t.description or "Custom tool",
                    "tool_id": str(t.id),
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
        "meta": "meta",
        "rag": "query",       # RAG is handled within query_agent
        "hybrid": "query",    # hybrid defaults to query path
        "build_connector": "tool",
        "build_tool": "tool",
    }
    return mapping.get(intent, "query")
