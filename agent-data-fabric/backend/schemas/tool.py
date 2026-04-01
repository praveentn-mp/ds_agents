"""Pydantic schemas for custom tools."""

from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel


class ToolCreate(BaseModel):
    name: str
    description: Optional[str] = None
    code: str
    input_schema: dict = {}


class ToolUpdate(BaseModel):
    description: Optional[str] = None
    code: Optional[str] = None
    input_schema: Optional[dict] = None
    is_active: Optional[bool] = None


class ToolResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    code: str
    input_schema: dict = {}
    current_version: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ToolExecuteRequest(BaseModel):
    arguments: dict = {}


class ToolExecutionResult(BaseModel):
    success: bool
    result: Optional[dict] = None
    error: Optional[str] = None
    duration_ms: int = 0


class ToolVersionResponse(BaseModel):
    id: UUID
    tool_id: UUID
    version: int
    code: str
    input_schema: dict = {}
    created_at: datetime

    model_config = {"from_attributes": True}
