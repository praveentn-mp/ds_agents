"""Pydantic schemas for observability."""

from datetime import datetime
from typing import Optional, Any
from uuid import UUID
from pydantic import BaseModel


class ObservabilitySummary(BaseModel):
    tokens_total: int
    tokens_input: int
    tokens_output: int
    tokens_cache: int
    avg_latency_ms: float
    total_calls: int
    top_models: list[dict]


class LLMCallEntry(BaseModel):
    id: UUID
    message_id: Optional[UUID] = None
    category: Optional[str] = None
    model: str
    tokens_input: int
    tokens_output: int
    tokens_cache: int
    latency_ms: int
    tool_calls: Optional[list] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class TraceStepResponse(BaseModel):
    id: UUID
    trace_type: str
    agent_name: Optional[str] = None
    tool_name: Optional[str] = None
    payload: Optional[dict] = None
    status: str
    duration_ms: Optional[int] = None
    sequence: int
    created_at: datetime

    model_config = {"from_attributes": True}
