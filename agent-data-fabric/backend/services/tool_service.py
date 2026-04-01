"""Custom tool service — CRUD, execution, versioning."""

import time
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from RestrictedPython import compile_restricted, safe_globals

from backend.models.custom_tool import CustomTool
from backend.models.tool_version import ToolVersion
from backend.models.mcp_tool import MCPTool


async def list_tools(db: AsyncSession) -> list[CustomTool]:
    result = await db.execute(select(CustomTool).order_by(CustomTool.created_at.desc()))
    return list(result.scalars().all())


async def get_tool(db: AsyncSession, tool_id: UUID) -> Optional[CustomTool]:
    result = await db.execute(select(CustomTool).where(CustomTool.id == tool_id))
    return result.scalar_one_or_none()


async def create_tool(db: AsyncSession, data: dict, owner_id: Optional[UUID] = None) -> CustomTool:
    tool = CustomTool(
        name=data["name"],
        description=data.get("description"),
        code=data["code"],
        input_schema=data.get("input_schema", {}),
        owner_id=owner_id,
    )
    db.add(tool)
    await db.flush()
    await db.refresh(tool)

    # Save initial version
    version = ToolVersion(
        tool_id=tool.id,
        version=1,
        code=data["code"],
        input_schema=data.get("input_schema", {}),
        created_by=owner_id,
    )
    db.add(version)

    # Auto-register as MCP tool
    mcp_tool = MCPTool(
        name=tool.name,
        description=tool.description,
        input_schema=tool.input_schema,
        source_type="custom_tool",
        source_id=tool.id,
    )
    db.add(mcp_tool)
    await db.flush()
    return tool


async def update_tool(db: AsyncSession, tool_id: UUID, data: dict, user_id: Optional[UUID] = None) -> Optional[CustomTool]:
    result = await db.execute(select(CustomTool).where(CustomTool.id == tool_id))
    tool = result.scalar_one_or_none()
    if not tool:
        return None

    if data.get("code"):
        tool.code = data["code"]
        tool.current_version += 1
        version = ToolVersion(
            tool_id=tool.id,
            version=tool.current_version,
            code=data["code"],
            input_schema=data.get("input_schema", tool.input_schema),
            created_by=user_id,
        )
        db.add(version)

    if data.get("description") is not None:
        tool.description = data["description"]
    if data.get("input_schema") is not None:
        tool.input_schema = data["input_schema"]
    if data.get("is_active") is not None:
        tool.is_active = data["is_active"]

    await db.flush()
    await db.refresh(tool)
    return tool


async def execute_tool(db: AsyncSession, tool_id: UUID, arguments: dict) -> dict:
    tool = await get_tool(db, tool_id)
    if not tool:
        return {"success": False, "error": "Tool not found", "duration_ms": 0}

    start = time.monotonic()
    try:
        # Sandboxed execution
        restricted_globals = safe_globals.copy()
        restricted_globals["_getattr_"] = getattr
        restricted_globals["_getitem_"] = lambda obj, key: obj[key]
        restricted_globals["__builtins__"]["__import__"] = None  # block imports

        byte_code = compile_restricted(tool.code, '<custom_tool>', 'exec')
        local_ns = {"arguments": arguments}
        exec(byte_code, restricted_globals, local_ns)

        result = local_ns.get("result", local_ns.get("output", None))
        duration = int((time.monotonic() - start) * 1000)
        return {"success": True, "result": result, "duration_ms": duration}
    except Exception as e:
        duration = int((time.monotonic() - start) * 1000)
        return {"success": False, "error": str(e), "duration_ms": duration}


async def get_tool_versions(db: AsyncSession, tool_id: UUID) -> list[ToolVersion]:
    result = await db.execute(
        select(ToolVersion).where(ToolVersion.tool_id == tool_id).order_by(ToolVersion.version.desc())
    )
    return list(result.scalars().all())
