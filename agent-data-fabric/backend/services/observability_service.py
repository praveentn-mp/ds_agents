"""Observability service — aggregations, token tracking."""

from typing import Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.llm_call import LLMCall
from backend.models.execution_trace import ExecutionTrace


async def get_summary(db: AsyncSession) -> dict:
    result = await db.execute(
        select(
            func.coalesce(func.sum(LLMCall.tokens_input), 0).label("tokens_input"),
            func.coalesce(func.sum(LLMCall.tokens_output), 0).label("tokens_output"),
            func.coalesce(func.sum(LLMCall.tokens_cache), 0).label("tokens_cache"),
            func.coalesce(func.avg(LLMCall.latency_ms), 0).label("avg_latency"),
            func.count(LLMCall.id).label("total_calls"),
        )
    )
    row = result.one()

    # Top models
    model_result = await db.execute(
        select(LLMCall.model, func.count(LLMCall.id).label("count"))
        .group_by(LLMCall.model)
        .order_by(func.count(LLMCall.id).desc())
        .limit(5)
    )
    top_models = [{"model": r.model, "count": r.count} for r in model_result.all()]

    return {
        "tokens_total": row.tokens_input + row.tokens_output,
        "tokens_input": row.tokens_input,
        "tokens_output": row.tokens_output,
        "tokens_cache": row.tokens_cache,
        "avg_latency_ms": float(row.avg_latency),
        "total_calls": row.total_calls,
        "top_models": top_models,
    }


async def get_llm_calls(db: AsyncSession, page: int = 1, page_size: int = 50) -> dict:
    offset = (page - 1) * page_size
    count_result = await db.execute(select(func.count(LLMCall.id)))
    total = count_result.scalar()

    result = await db.execute(
        select(LLMCall).order_by(LLMCall.created_at.desc()).offset(offset).limit(page_size)
    )
    calls = result.scalars().all()
    return {"total": total, "page": page, "page_size": page_size, "items": calls}


async def get_traces(db: AsyncSession, message_id: UUID) -> list[ExecutionTrace]:
    result = await db.execute(
        select(ExecutionTrace)
        .where(ExecutionTrace.message_id == message_id)
        .order_by(ExecutionTrace.sequence)
    )
    return list(result.scalars().all())
