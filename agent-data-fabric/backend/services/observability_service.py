"""Observability service — aggregations, token tracking."""

from typing import Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.llm_call import LLMCall
from backend.models.execution_trace import ExecutionTrace


async def get_summary(db: AsyncSession, category: Optional[str] = None) -> dict:
    base_query = select(
        func.coalesce(func.sum(LLMCall.tokens_input), 0).label("tokens_input"),
        func.coalesce(func.sum(LLMCall.tokens_output), 0).label("tokens_output"),
        func.coalesce(func.sum(LLMCall.tokens_cache), 0).label("tokens_cache"),
        func.coalesce(func.avg(LLMCall.latency_ms), 0).label("avg_latency"),
        func.count(LLMCall.id).label("total_calls"),
    )
    if category:
        base_query = base_query.where(LLMCall.category == category)
    result = await db.execute(base_query)
    row = result.one()

    # Top models
    model_query = (
        select(LLMCall.model, func.count(LLMCall.id).label("count"))
        .group_by(LLMCall.model)
        .order_by(func.count(LLMCall.id).desc())
        .limit(5)
    )
    if category:
        model_query = model_query.where(LLMCall.category == category)
    model_result = await db.execute(model_query)
    top_models = [{"model": r.model, "count": r.count} for r in model_result.all()]

    # Category breakdown
    cat_result = await db.execute(
        select(
            LLMCall.category,
            func.count(LLMCall.id).label("count"),
            func.coalesce(func.sum(LLMCall.tokens_input + LLMCall.tokens_output), 0).label("tokens"),
        )
        .group_by(LLMCall.category)
        .order_by(func.count(LLMCall.id).desc())
    )
    categories = [{"category": r.category or "unknown", "count": r.count, "tokens": r.tokens} for r in cat_result.all()]

    return {
        "tokens_total": row.tokens_input + row.tokens_output,
        "tokens_input": row.tokens_input,
        "tokens_output": row.tokens_output,
        "tokens_cache": row.tokens_cache,
        "avg_latency_ms": float(row.avg_latency),
        "total_calls": row.total_calls,
        "top_models": top_models,
        "categories": categories,
    }


async def get_llm_calls(db: AsyncSession, page: int = 1, page_size: int = 50, category: Optional[str] = None) -> dict:
    offset = (page - 1) * page_size

    count_query = select(func.count(LLMCall.id))
    if category:
        count_query = count_query.where(LLMCall.category == category)
    count_result = await db.execute(count_query)
    total = count_result.scalar()

    items_query = select(LLMCall).order_by(LLMCall.created_at.desc()).offset(offset).limit(page_size)
    if category:
        items_query = items_query.where(LLMCall.category == category)
    result = await db.execute(items_query)
    calls = result.scalars().all()

    # Serialize ORM objects to dicts to avoid MetaData() class attribute leaking
    items = []
    for c in calls:
        items.append({
            "id": str(c.id),
            "message_id": str(c.message_id) if c.message_id else None,
            "conversation_id": str(c.conversation_id) if c.conversation_id else None,
            "category": c.category or "unknown",
            "model": c.model,
            "tokens_input": c.tokens_input,
            "tokens_output": c.tokens_output,
            "tokens_cache": c.tokens_cache,
            "latency_ms": c.latency_ms,
            "tool_calls": c.tool_calls,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        })
    return {"total": total, "page": page, "page_size": page_size, "items": items}


async def get_traces(db: AsyncSession, message_id: UUID) -> list[ExecutionTrace]:
    result = await db.execute(
        select(ExecutionTrace)
        .where(ExecutionTrace.message_id == message_id)
        .order_by(ExecutionTrace.sequence)
    )
    return list(result.scalars().all())
