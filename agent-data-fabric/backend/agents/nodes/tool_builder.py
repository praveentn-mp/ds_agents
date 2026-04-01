"""Tool builder agent node."""

from backend.agents.state import ADFAgentState
from backend.agents.llm import get_llm


async def tool_builder(state: ADFAgentState) -> dict:
    """Build custom tools via LLM code generation."""
    llm = get_llm()
    user_message = state["messages"][-1]["content"]

    prompt = f"""You are a tool builder assistant. The user wants to create a new custom tool.

Request: "{user_message}"

Generate Python code for the tool, explain its inputs and outputs, and provide the input schema.
The code should be safe to run in a sandboxed environment (no file I/O, no network, no imports)."""

    try:
        response = await llm.ainvoke(prompt)
        final_response = response.content
    except Exception as e:
        final_response = f"I'd help you build that tool, but encountered an issue: {str(e)}"

    return {
        "final_response": final_response,
        "current_step": 3,
        "trace_events": [{
            "type": "tool_call",
            "agent": "tool_builder",
            "status": "success",
            "payload": {"request": user_message},
            "sequence": 3,
        }],
    }
