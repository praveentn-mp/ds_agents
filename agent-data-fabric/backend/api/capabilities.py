"""Capabilities API — unified listing of all system capabilities."""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models.connector import Connector
from backend.models.mcp_tool import MCPTool
from backend.models.custom_tool import CustomTool
from backend.models.mcp_prompt import MCPPrompt
from backend.middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/capabilities", tags=["capabilities"])


@router.get("")
async def list_capabilities(db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    connectors = await db.execute(
        select(Connector).where(Connector.is_active == True)
    )
    mcp_tools = await db.execute(
        select(MCPTool).where(MCPTool.is_active == True)
    )
    custom_tools = await db.execute(
        select(CustomTool).where(CustomTool.is_active == True)
    )
    prompts = await db.execute(select(MCPPrompt))

    return {
        "connectors": [
            {"id": str(c.id), "name": c.name, "type": c.connector_type, "description": c.description}
            for c in connectors.scalars().all()
        ],
        "mcp_tools": [
            {"id": str(t.id), "name": t.name, "description": t.description, "source": t.source_type}
            for t in mcp_tools.scalars().all()
        ],
        "custom_tools": [
            {"id": str(t.id), "name": t.name, "description": t.description}
            for t in custom_tools.scalars().all()
        ],
        "prompts": [
            {"id": str(p.id), "name": p.name, "description": p.description}
            for p in prompts.scalars().all()
        ],
    }
