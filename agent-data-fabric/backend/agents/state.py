"""Agent state definition for LangGraph."""

from typing import TypedDict, Optional, Annotated
from operator import add


class ADFAgentState(TypedDict):
    conversation_id: str
    user_id: str
    user_role: str
    messages: list[dict]
    intent: Optional[str]
    route: Optional[str]
    capabilities: list[dict]
    plan_steps: list[dict]
    current_step: int
    trace_events: Annotated[list[dict], add]
    llm_calls: Annotated[list[dict], add]
    final_response: Optional[str]
    error: Optional[str]
    token_count: dict
