"""Pydantic schemas for SQL Explorer."""

from datetime import datetime
from typing import Optional, Any
from uuid import UUID
from pydantic import BaseModel


class SQLExecuteRequest(BaseModel):
    query: str
    connector_id: UUID
    page: int = 1
    page_size: int = 50


class SQLExecuteResult(BaseModel):
    columns: list[str]
    rows: list[list[Any]]
    total: int
    page: int
    page_size: int
    latency_ms: int


class SQLHistoryEntry(BaseModel):
    id: UUID
    query: str
    connector_id: Optional[UUID] = None
    row_count: Optional[int] = None
    duration_ms: Optional[int] = None
    error: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
