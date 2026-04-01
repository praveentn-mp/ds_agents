"""Ingestion API — trigger data ingestion, reindex, delete, and search with SSE progress."""

import json
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.services.ingestion_service import (
    start_ingestion, get_ingestion_status, get_connector_data_summary,
    delete_connector_data, reindex_connector,
)
from backend.services.search_service import hybrid_search
from backend.middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/connectors", tags=["ingestion"])


class IngestRequest(BaseModel):
    table_names: Optional[list[str]] = None
    file_names: Optional[list[str]] = None


@router.post("/{connector_id}/ingest")
async def ingest(
    connector_id: UUID,
    body: Optional[IngestRequest] = None,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Start data ingestion from a connector. Returns SSE stream with progress events.
    For postgres connectors, pass table_names to select which tables to index.
    For blob/filesystem connectors, pass file_names to select which files to ingest.
    """
    table_names = body.table_names if body else None
    file_names = body.file_names if body else None

    async def event_stream():
        async for event in start_ingestion(db, connector_id, user.id, table_names=table_names, file_names=file_names):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/{connector_id}/ingest/status")
async def ingest_status(
    connector_id: UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Get the latest ingestion job status."""
    return await get_ingestion_status(db, connector_id)


@router.get("/{connector_id}/data-summary")
async def data_summary(
    connector_id: UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Get a summary of data available through this connector including vector index counts."""
    return await get_connector_data_summary(db, connector_id)


@router.post("/{connector_id}/reindex")
async def reindex(
    connector_id: UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Delete existing index data and re-run ingestion for a connector."""

    async def event_stream():
        async for event in reindex_connector(db, connector_id, user.id):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.delete("/{connector_id}/data")
async def delete_data(
    connector_id: UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Delete all ingested data (tables + vector indices) for a connector."""
    result = await delete_connector_data(db, connector_id)
    return {"message": "Data deleted successfully", **result}


# ── Search endpoint (not connector-scoped) ──

search_router = APIRouter(prefix="/search", tags=["search"])


@search_router.post("")
async def search(
    data: dict,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Hybrid vector search across all indices."""
    query = data.get("query", "")
    if not query:
        raise HTTPException(status_code=400, detail="query is required")

    result = await hybrid_search(
        query=query,
        db=db,
        top_k=data.get("top_k", 10),
        min_score=data.get("min_score", 0.25),
        connector_id=data.get("connector_id"),
    )
    return result.to_dict()
