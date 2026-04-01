"""Pydantic schemas for MCP layer."""

from datetime import datetime
from typing import Optional, Any
from uuid import UUID
from pydantic import BaseModel, Field


class MCPServerCreate(BaseModel):
    name: str
    image: str
    config: dict = {}
    auto_register: bool = True


class MCPServerResponse(BaseModel):
    id: UUID
    name: str
    image: Optional[str] = None
    container_id: Optional[str] = None
    sse_url: Optional[str] = None
    status: str
    config: dict = {}
    is_enabled: bool
    tool_count: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class MCPResourceResponse(BaseModel):
    id: UUID
    uri: str
    name: str
    description: Optional[str] = None
    resource_type: str
    source_type: str
    mime_type: Optional[str] = None
    resource_schema: Optional[dict] = Field(default=None, validation_alias="schema_json")
    last_updated: datetime

    model_config = {"from_attributes": True}


class MCPToolResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    input_schema: dict = {}
    source_type: str
    server_name: Optional[str] = None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class MCPPromptResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str] = None
    template: str
    variables: list = []
    created_at: datetime

    model_config = {"from_attributes": True}


class MCPPromptRender(BaseModel):
    prompt_name: str
    variables: dict = {}


class MCPToolDryRun(BaseModel):
    tool_name: str
    arguments: dict = {}
