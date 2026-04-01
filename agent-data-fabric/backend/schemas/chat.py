"""Pydantic schemas for chat and conversations."""

from datetime import datetime
from typing import Optional, Any
from uuid import UUID
from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[UUID] = None


class MessageResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    role: str
    content: str
    metadata: Optional[dict] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ConversationResponse(BaseModel):
    id: UUID
    title: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TraceEvent(BaseModel):
    type: str
    agent: Optional[str] = None
    tool: Optional[str] = None
    status: str = "running"
    payload: Optional[dict] = None
    sequence: int = 0
    duration_ms: Optional[int] = None
