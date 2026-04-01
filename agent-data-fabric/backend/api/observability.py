"""Observability API — metrics, traces, LLM call history."""

from uuid import UUID
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.schemas.observability import ObservabilitySummary, LLMCallEntry, TraceStepResponse
from backend.services.observability_service import get_summary, get_llm_calls, get_traces
from backend.middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/observability", tags=["observability"])


@router.get("/summary", response_model=ObservabilitySummary)
async def summary(db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    return await get_summary(db)


@router.get("/llm-calls")
async def llm_calls(
    page: int = 1,
    page_size: int = 50,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    return await get_llm_calls(db, page, page_size)


@router.get("/traces/{message_id}", response_model=list[TraceStepResponse])
async def traces(message_id: UUID, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    return await get_traces(db, message_id)
