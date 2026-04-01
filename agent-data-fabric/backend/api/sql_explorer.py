"""SQL Explorer API — execute queries, history, schema browser, pagination."""

import time
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from backend.database import get_db
from backend.schemas.sql import SQLExecuteRequest, SQLExecuteResult, SQLHistoryEntry
from backend.models.sql_query_history import SQLQueryHistory
from backend.models.connector import Connector
from backend.services.connector_service import _build_connector
from backend.middleware.auth_middleware import get_current_user, require_permission

router = APIRouter(prefix="/sql", tags=["sql-explorer"])


@router.get("/schema/{connector_id}")
async def get_schema(
    connector_id: UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Return table/column schema for a postgres connector."""
    result = await db.execute(select(Connector).where(Connector.id == connector_id))
    connector = result.scalar_one_or_none()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    if connector.connector_type != "postgres":
        raise HTTPException(status_code=400, detail="Schema browsing only supported for postgres connectors")

    try:
        instance = _build_connector(connector)
        schema = await instance.discover_schema()
        await instance.close()
        return schema
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute", response_model=SQLExecuteResult)
async def execute_sql(
    data: SQLExecuteRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(require_permission("execute_sql_read")),
):
    # Validate connector exists
    result = await db.execute(select(Connector).where(Connector.id == data.connector_id))
    connector = result.scalar_one_or_none()
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")

    # Block write operations for read-only permission
    query_upper = data.query.strip().upper()
    if any(query_upper.startswith(kw) for kw in ["INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE", "CREATE"]):
        # Check write permission
        if user.role:
            perms = user.role.permissions or []
            if "execute_sql_write" not in perms:
                raise HTTPException(status_code=403, detail="Write permission required")

    start = time.monotonic()
    try:
        instance = _build_connector(connector)
        rows = await instance.execute_query(data.query)
        await instance.close()
        duration = int((time.monotonic() - start) * 1000)

        total = len(rows)
        offset = (data.page - 1) * data.page_size
        page_rows = rows[offset : offset + data.page_size]

        columns = list(page_rows[0].keys()) if page_rows else []
        row_data = [list(r.values()) for r in page_rows]

        # Log history
        history = SQLQueryHistory(
            user_id=user.id,
            connector_id=data.connector_id,
            query=data.query,
            row_count=total,
            duration_ms=duration,
        )
        db.add(history)

        return SQLExecuteResult(
            columns=columns,
            rows=row_data,
            total=total,
            page=data.page,
            page_size=data.page_size,
            latency_ms=duration,
        )
    except Exception as e:
        duration = int((time.monotonic() - start) * 1000)
        history = SQLQueryHistory(
            user_id=user.id,
            connector_id=data.connector_id,
            query=data.query,
            duration_ms=duration,
            error=str(e)[:500],
        )
        db.add(history)
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/history", response_model=list[SQLHistoryEntry])
async def history(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    result = await db.execute(
        select(SQLQueryHistory)
        .where(SQLQueryHistory.user_id == user.id)
        .order_by(SQLQueryHistory.created_at.desc())
        .limit(100)
    )
    return list(result.scalars().all())
