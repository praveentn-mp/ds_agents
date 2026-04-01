"""MCP service — server management, registry queries."""

from typing import Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.mcp_server import MCPServer
from backend.models.mcp_resource import MCPResource
from backend.models.mcp_tool import MCPTool
from backend.models.mcp_prompt import MCPPrompt


async def list_servers(db: AsyncSession) -> list[dict]:
    result = await db.execute(select(MCPServer).order_by(MCPServer.created_at.desc()))
    servers = result.scalars().all()
    output = []
    for s in servers:
        tool_count_result = await db.execute(
            select(func.count(MCPTool.id)).where(MCPTool.server_name == s.name)
        )
        tool_count = tool_count_result.scalar() or 0
        output.append({
            "id": s.id,
            "name": s.name,
            "image": s.image,
            "container_id": s.container_id,
            "sse_url": s.sse_url,
            "status": s.status,
            "config": s.config,
            "is_enabled": s.is_enabled,
            "tool_count": tool_count,
            "created_at": s.created_at,
        })
    return output


async def get_server(db: AsyncSession, server_id: UUID) -> Optional[MCPServer]:
    result = await db.execute(select(MCPServer).where(MCPServer.id == server_id))
    return result.scalar_one_or_none()


async def create_server(db: AsyncSession, data: dict) -> MCPServer:
    server = MCPServer(
        name=data["name"],
        image=data.get("image"),
        config=data.get("config", {}),
        auto_register=data.get("auto_register", True),
    )
    db.add(server)
    await db.flush()
    await db.refresh(server)
    return server


async def list_resources(db: AsyncSession) -> list[MCPResource]:
    result = await db.execute(select(MCPResource).order_by(MCPResource.last_updated.desc()))
    return list(result.scalars().all())


async def list_tools(db: AsyncSession) -> list[MCPTool]:
    """List MCP tools, deduplicated by name (keeps latest per name)."""
    result = await db.execute(
        select(MCPTool).where(MCPTool.is_active == True).order_by(MCPTool.created_at.desc())
    )
    all_tools = list(result.scalars().all())
    seen = set()
    deduped = []
    for t in all_tools:
        if t.name not in seen:
            seen.add(t.name)
            deduped.append(t)
    return deduped


async def list_prompts(db: AsyncSession) -> list[MCPPrompt]:
    result = await db.execute(select(MCPPrompt).order_by(MCPPrompt.created_at.desc()))
    return list(result.scalars().all())


async def render_prompt(db: AsyncSession, prompt_name: str, variables: dict) -> str:
    result = await db.execute(select(MCPPrompt).where(MCPPrompt.name == prompt_name))
    prompt = result.scalar_one_or_none()
    if not prompt:
        raise ValueError(f"Prompt '{prompt_name}' not found")
    rendered = prompt.template
    for key, value in variables.items():
        rendered = rendered.replace("{{" + key + "}}", str(value))
    return rendered
