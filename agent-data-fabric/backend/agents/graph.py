"""Agent graph — LangGraph orchestration."""

import time
import json
from typing import AsyncIterator
from sqlalchemy.ext.asyncio import AsyncSession

from langgraph.graph import StateGraph, END

from backend.agents.state import ADFAgentState
from backend.agents.nodes.orchestrator import classify_intent, resolve_capabilities, route_decision
from backend.agents.nodes.query_agent import query_agent
from backend.agents.nodes.tool_agent import tool_agent
from backend.agents.nodes.rag_agent import rag_agent
from backend.models.message import Message
from backend.models.execution_trace import ExecutionTrace
from backend.models.llm_call import LLMCall


def build_graph() -> StateGraph:
    graph = StateGraph(ADFAgentState)

    # Add nodes
    graph.add_node("classify_intent", classify_intent)
    graph.add_node("resolve_capabilities", resolve_capabilities)
    graph.add_node("query_agent", query_agent)
    graph.add_node("tool_agent", tool_agent)
    graph.add_node("rag_agent", rag_agent)
    graph.add_node("response_formatter", response_formatter)
    graph.add_node("error_handler", error_handler)

    # Set entry point
    graph.set_entry_point("classify_intent")

    # Edges
    graph.add_edge("classify_intent", "resolve_capabilities")
    graph.add_conditional_edges(
        "resolve_capabilities",
        route_decision,
        {
            "query": "query_agent",
            "tool": "tool_agent",
            "rag": "rag_agent",
            "hybrid": "query_agent",
            "error": "error_handler",
        },
    )
    graph.add_edge("query_agent", "response_formatter")
    graph.add_edge("tool_agent", "response_formatter")
    graph.add_edge("rag_agent", "response_formatter")
    graph.add_edge("response_formatter", END)
    graph.add_edge("error_handler", END)

    return graph


def response_formatter(state: ADFAgentState) -> dict:
    """Format final response from agent execution."""
    if state.get("error"):
        return {
            "final_response": f"I encountered an issue: {state['error']}",
            "trace_events": [{
                "type": "response",
                "status": "error",
                "payload": {"error": state["error"]},
                "sequence": state.get("current_step", 0) + 1,
            }],
        }
    return {
        "trace_events": [{
            "type": "response",
            "status": "success",
            "payload": {"response": state.get("final_response", "")},
            "sequence": state.get("current_step", 0) + 1,
        }],
    }


def error_handler(state: ADFAgentState) -> dict:
    error = state.get("error", "Unknown error occurred")
    return {
        "final_response": f"Sorry, I encountered an error: {error}. Please try again.",
        "trace_events": [{
            "type": "error",
            "status": "error",
            "payload": {"error": error},
            "sequence": state.get("current_step", 0) + 1,
        }],
    }


_compiled_graph = None


def get_compiled_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph().compile()
    return _compiled_graph


async def run_agent(
    message: str,
    conversation_id: str,
    user_id: str,
    user_role: str,
    db: AsyncSession,
) -> AsyncIterator[dict]:
    """Run the agent graph and yield SSE events."""
    graph = get_compiled_graph()
    start = time.monotonic()

    initial_state = {
        "conversation_id": conversation_id,
        "user_id": user_id,
        "user_role": user_role,
        "messages": [{"role": "user", "content": message}],
        "intent": None,
        "route": None,
        "capabilities": [],
        "plan_steps": [],
        "current_step": 0,
        "trace_events": [],
        "llm_calls": [],
        "final_response": None,
        "error": None,
        "token_count": {"input": 0, "output": 0, "cache": 0},
    }

    try:
        result = await graph.ainvoke(initial_state)

        # Emit trace events
        for event in result.get("trace_events", []):
            yield {
                "event": "trace_step",
                "data": event,
            }

        # Emit final response as tokens
        final_response = result.get("final_response", "I processed your request but have no additional information to share.")
        if final_response:
            yield {
                "event": "token",
                "data": {"content": final_response},
            }

            # Save assistant message
            assistant_msg = Message(
                conversation_id=conversation_id,
                role="assistant",
                content=final_response,
                message_metadata={"trace_events": result.get("trace_events", [])},
            )
            db.add(assistant_msg)
            await db.flush()
            await db.refresh(assistant_msg)

            # Save LLM call records to DB for observability
            for call_data in result.get("llm_calls", []):
                llm_record = LLMCall(
                    message_id=assistant_msg.id,
                    conversation_id=conversation_id,
                    model=call_data.get("model", "unknown"),
                    tokens_input=call_data.get("tokens_input", 0),
                    tokens_output=call_data.get("tokens_output", 0),
                    tokens_cache=call_data.get("tokens_cache", 0),
                    latency_ms=call_data.get("latency_ms", 0),
                    tool_calls={"node": call_data.get("node", "")},
                )
                db.add(llm_record)
            await db.flush()

        duration = int((time.monotonic() - start) * 1000)
        token_count = result.get("token_count", {"input": 0, "output": 0, "cache": 0})

        # Determine model from LLM calls
        llm_calls = result.get("llm_calls", [])
        model_name = llm_calls[0].get("model", "unknown") if llm_calls else "unknown"

        # Determine which system prompt was used
        intent = result.get("intent", "query")
        prompt_mapping = {
            "query": "query_planner",
            "tool": "tool_selector",
            "rag": "query_planner",
            "hybrid": "connector_vs_tool_decider",
            "build_connector": "connector_vs_tool_decider",
            "build_tool": "tool_selector",
        }
        prompt_used = prompt_mapping.get(intent, "tool_selector")

        yield {
            "event": "done",
            "data": {
                "conversation_id": conversation_id,
                "tokens": token_count,
                "latency_ms": duration,
                "llm_calls_count": len(llm_calls),
                "model": model_name,
                "prompt_used": prompt_used,
            },
        }

    except Exception as e:
        yield {
            "event": "error",
            "data": {"message": str(e)},
        }
        yield {
            "event": "done",
            "data": {"conversation_id": conversation_id, "tokens": {}, "latency_ms": 0},
        }
