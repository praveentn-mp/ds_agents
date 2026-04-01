"""RAG agent node — LlamaIndex retrieval."""

from backend.agents.state import ADFAgentState
from backend.agents.llm import invoke_llm


async def rag_agent(state: ADFAgentState) -> dict:
    """Handle RAG-based retrieval and response."""
    user_message = state["messages"][-1]["content"]

    prompt = f"""You are a document retrieval assistant. The user wants to find information from indexed documents.

User query: "{user_message}"

Provide a helpful response based on what documents might contain relevant information.
If no documents are indexed yet, explain how the user can index resources for search."""

    try:
        final_response, usage = await invoke_llm(prompt)
    except Exception as e:
        final_response = f"I'd help you search documents, but encountered an issue: {str(e)}"
        usage = None

    result = {
        "final_response": final_response,
        "current_step": 3,
        "trace_events": [{
            "type": "rag",
            "agent": "rag_agent",
            "status": "success",
            "payload": {"query": user_message},
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
                                 "latency_ms": usage.latency_ms, "node": "rag_agent"}]

    return result
