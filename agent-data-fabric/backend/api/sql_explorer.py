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

# Internal ADF tables that should be hidden from user-facing schema browser
_INTERNAL_TABLES = {
    "users", "roles", "connectors", "connector_schemas", "conversations", "messages",
    "llm_calls", "sync_jobs", "custom_tools", "tool_versions", "mcp_servers",
    "execution_traces", "sql_query_history", "alembic_version",
    "vec_table_index", "vec_column_index", "vec_value_index", "vec_chunk_index",
    "ingestion_metadata", "column_metadata",
}


@router.get("/schema/{connector_id}")
async def get_schema(
    connector_id: UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Return table/column schema for a postgres connector (internal tables filtered out)."""
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
        # Filter out internal ADF tables
        if "tables" in schema:
            schema["tables"] = [
                t for t in schema["tables"]
                if t.get("name") not in _INTERNAL_TABLES
            ]
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


VECTOR_TABLES = ["vec_table_index", "vec_column_index", "vec_value_index", "vec_chunk_index"]


@router.get("/vector-schema")
async def vector_schema(
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    """Return schema and row counts for internal vector index tables."""
    tables = []
    for table_name in VECTOR_TABLES:
        try:
            cols_result = await db.execute(text(
                "SELECT column_name, data_type FROM information_schema.columns "
                "WHERE table_name = :tn AND table_schema = 'public' ORDER BY ordinal_position"
            ), {"tn": table_name})
            columns = [{"name": r[0], "type": r[1]} for r in cols_result.fetchall()]
            if not columns:
                continue
            count_result = await db.execute(text(f'SELECT COUNT(*) FROM "{table_name}"'))
            row_count = count_result.scalar() or 0
            tables.append({"name": table_name, "columns": columns, "row_count": row_count})
        except Exception:
            continue
    return {"tables": tables}
