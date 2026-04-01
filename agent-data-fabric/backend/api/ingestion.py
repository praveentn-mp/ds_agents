"""Ingestion API — trigger data ingestion from connectors with SSE progress."""

import json
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.services.ingestion_service import start_ingestion, get_ingestion_status, get_connector_data_summary
from backend.middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/connectors", tags=["ingestion"])


@router.post("/{connector_id}/ingest")
async def ingest(
    connector_id: UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Start data ingestion from a connector. Returns SSE stream with progress events."""

    async def event_stream():
        async for event in start_ingestion(db, connector_id, user.id):
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
    """Get a summary of data available through this connector."""
    return await get_connector_data_summary(db, connector_id)
