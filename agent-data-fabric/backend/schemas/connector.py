"""Pydantic schemas for connectors."""

from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field


class ConnectorCreate(BaseModel):
    name: str
    connector_type: str
    description: Optional[str] = None
    config: dict = {}
    credentials: Optional[dict] = None
    sync_mode: str = "live"
    sync_interval_seconds: int = 3600


class ConnectorUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    config: Optional[dict] = None
    credentials: Optional[dict] = None
    sync_mode: Optional[str] = None
    sync_interval_seconds: Optional[int] = None
    is_active: Optional[bool] = None


class ConnectorResponse(BaseModel):
    id: UUID
    name: str
    connector_type: str
    description: Optional[str] = None
    config: dict = {}
    sync_mode: str
    is_active: bool
    last_synced_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConnectorTestResult(BaseModel):
    success: bool
    latency_ms: int
    message: str = ""


class SchemaDiscoveryResult(BaseModel):
    connector_id: UUID
    version: int
    discovered_schema: dict = Field(validation_alias="schema_json")
    discovered_at: datetime
