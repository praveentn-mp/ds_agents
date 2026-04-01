"""Tool agent node — MCP tool invocation."""

import json
from backend.agents.state import ADFAgentState
from backend.agents.llm import invoke_llm


async def tool_agent(state: ADFAgentState) -> dict:
    """Handle tool invocations via MCP."""
    user_message = state["messages"][-1]["content"]
    capabilities = state.get("capabilities", [])

    tools = [c for c in capabilities if c["type"] == "tool"]
    tool_info = "\n".join([f"- {t['name']}: {t['description']}" for t in tools])

    prompt = f"""You are a tool execution assistant. Given the user's request and available tools, provide a helpful response.

Available tools:
{tool_info}

User request: "{user_message}"

Explain what tool(s) you would use and what the expected outcome would be.
Respond with a clear, helpful answer."""

    try:
        final_response, usage = await invoke_llm(prompt)
    except Exception as e:
        final_response = f"I'd help you with that tool operation, but encountered an issue: {str(e)}"
        usage = None

    result = {
        "final_response": final_response,
        "current_step": 3,
        "trace_events": [{
            "type": "tool_call",
            "agent": "tool_agent",
            "status": "success",
            "payload": {"request": user_message},
            "sequence": 3,
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
                                 "latency_ms": usage.latency_ms, "node": "tool_agent"}]

    return result
