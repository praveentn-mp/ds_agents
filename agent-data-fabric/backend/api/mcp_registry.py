"""MCP Registry API — resources, tools, prompts read."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.schemas.mcp import (
    MCPResourceResponse, MCPToolResponse, MCPPromptResponse,
    MCPPromptRender, MCPToolDryRun,
)
from backend.services.mcp_service import list_resources, list_tools, list_prompts, render_prompt
from backend.middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/mcp/registry", tags=["mcp-registry"])


@router.get("/resources", response_model=list[MCPResourceResponse])
async def get_resources(db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    return await list_resources(db)


@router.get("/tools", response_model=list[MCPToolResponse])
async def get_tools(db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    return await list_tools(db)


@router.get("/prompts", response_model=list[MCPPromptResponse])
async def get_prompts(db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    return await list_prompts(db)


@router.post("/prompts/render")
async def render(data: MCPPromptRender, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    try:
        rendered = await render_prompt(db, data.prompt_name, data.variables)
        return {"rendered": rendered}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/tools/dry-run")
async def dry_run(data: MCPToolDryRun, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    return {
        "tool_name": data.tool_name,
        "arguments": data.arguments,
        "result": "Dry run — no execution",
        "note": "Connect to MCP server for live execution",
    }
