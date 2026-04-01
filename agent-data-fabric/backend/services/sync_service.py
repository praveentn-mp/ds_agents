"""Sync service — background data sync for connectors."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.connector import Connector
from backend.models.sync_job import SyncJob


async def create_sync_job(db: AsyncSession, connector_id: UUID) -> SyncJob:
    job = SyncJob(connector_id=connector_id, status="running")
    db.add(job)
    await db.flush()
    return job


async def complete_sync_job(db: AsyncSession, job_id: UUID, rows_synced: int = 0, error: str = None):
    result = await db.execute(select(SyncJob).where(SyncJob.id == job_id))
    job = result.scalar_one_or_none()
    if job:
        job.status = "failed" if error else "completed"
        job.rows_synced = rows_synced
        job.error_message = error
        job.completed_at = datetime.now(timezone.utc)
        await db.flush()
