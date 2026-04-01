"""Chat API — SSE streaming conversation with agent."""

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.schemas.chat import ChatRequest, MessageResponse, ConversationResponse
from backend.models.conversation import Conversation
from backend.models.message import Message
from backend.middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("")
async def chat(
    data: ChatRequest,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    # Get or create conversation
    if data.conversation_id:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == data.conversation_id,
                Conversation.user_id == user.id,
            )
        )
        conversation = result.scalar_one_or_none()
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        conversation = Conversation(
            user_id=user.id,
            title=data.message[:50] + "..." if len(data.message) > 50 else data.message,
        )
        db.add(conversation)
        await db.flush()
        await db.refresh(conversation)

    # Save user message
    user_msg = Message(
        conversation_id=conversation.id,
        role="user",
        content=data.message,
    )
    db.add(user_msg)
    await db.flush()

    # Run agent and stream response
    async def event_stream():
        try:
            from backend.agents.graph import run_agent

            async for event in run_agent(
                message=data.message,
                conversation_id=str(conversation.id),
                user_id=str(user.id),
                user_role=user.role.name if user.role else "viewer",
                db=db,
            ):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'event': 'error', 'data': {'message': str(e)}})}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.get("/conversations", response_model=list[ConversationResponse])
async def list_conversations(db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.user_id == user.id)
        .order_by(Conversation.updated_at.desc())
    )
    return list(result.scalars().all())


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageResponse])
async def get_messages(
    conversation_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user=Depends(get_current_user),
):
    # Verify ownership
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Conversation not found")

    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    return list(result.scalars().all())
