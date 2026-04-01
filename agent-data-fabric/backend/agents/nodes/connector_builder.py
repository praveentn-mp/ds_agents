"""Connector builder agent node."""

from backend.agents.state import ADFAgentState
from backend.agents.llm import get_llm


async def connector_builder(state: ADFAgentState) -> dict:
    """Build new connectors via LLM code generation."""
    llm = get_llm()
    user_message = state["messages"][-1]["content"]

    prompt = f"""You are a connector builder assistant. The user wants to create a new data connector.

Request: "{user_message}"

Explain what connector would be created, what configuration is needed, and provide a skeleton implementation."""

    try:
        response = await llm.ainvoke(prompt)
        final_response = response.content
    except Exception as e:
        final_response = f"I'd help you build that connector, but encountered an issue: {str(e)}"

    return {
        "final_response": final_response,
        "current_step": 3,
        "trace_events": [{
            "type": "tool_call",
            "agent": "connector_builder",
            "status": "success",
            "payload": {"request": user_message},
            "sequence": 3,
        }],
    }
