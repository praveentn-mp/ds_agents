"""Internal API — unauthenticated endpoints for MCP server inter-process calls.

These endpoints are only for server-to-server communication on localhost.
"""

from uuid import UUID
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.services.tool_service import list_tools, execute_tool
from backend.services.mcp_service import list_tools as list_mcp_tools

router = APIRouter(prefix="/internal", tags=["internal"])


class InternalToolExec(BaseModel):
    tool_name: str
    arguments: dict = {}


@router.get("/tools")
async def internal_list_tools(db: AsyncSession = Depends(get_db)):
    """List custom tools (no auth — for MCP server)."""
    tools = await list_tools(db)
    return [
        {
            "id": str(t.id),
            "name": t.name,
            "description": t.description,
            "input_schema": t.input_schema,
            "is_active": t.is_active,
        }
        for t in tools
    ]


@router.post("/tools/execute")
async def internal_execute_tool(data: InternalToolExec, db: AsyncSession = Depends(get_db)):
    """Execute a custom tool by name (no auth — for MCP server)."""
    from sqlalchemy import select
    from backend.models.custom_tool import CustomTool

    result = await db.execute(
        select(CustomTool).where(CustomTool.name == data.tool_name, CustomTool.is_active == True)
    )
    tool = result.scalar_one_or_none()
    if not tool:
        raise HTTPException(status_code=404, detail=f"Tool '{data.tool_name}' not found")
    return await execute_tool(db, tool.id, data.arguments)


@router.get("/mcp-tools")
async def internal_list_mcp_tools(db: AsyncSession = Depends(get_db)):
    """List MCP tools (no auth — for MCP server)."""
    return await list_mcp_tools(db)
