"""Custom Tools API — CRUD, execute, versions."""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.schemas.tool import (
    ToolCreate, ToolUpdate, ToolResponse, ToolExecuteRequest,
    ToolExecutionResult, ToolVersionResponse,
)
from backend.services.tool_service import (
    list_tools, get_tool, create_tool, update_tool, execute_tool, get_tool_versions,
)
from backend.middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("", response_model=list[ToolResponse])
async def list_all(db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    return await list_tools(db)


@router.post("", response_model=ToolResponse, status_code=201)
async def create(data: ToolCreate, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    tool = await create_tool(db, data.model_dump(), owner_id=user.id)
    return tool


@router.get("/{tool_id}", response_model=ToolResponse)
async def get_one(tool_id: UUID, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    tool = await get_tool(db, tool_id)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return tool


@router.put("/{tool_id}", response_model=ToolResponse)
async def update(tool_id: UUID, data: ToolUpdate, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    tool = await update_tool(db, tool_id, data.model_dump(exclude_unset=True), user_id=user.id)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return tool


@router.post("/{tool_id}/execute", response_model=ToolExecutionResult)
async def execute(tool_id: UUID, data: ToolExecuteRequest, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    result = await execute_tool(db, tool_id, data.arguments)
    return result


@router.get("/{tool_id}/versions", response_model=list[ToolVersionResponse])
async def versions(tool_id: UUID, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    return await get_tool_versions(db, tool_id)
