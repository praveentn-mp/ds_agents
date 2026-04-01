"""MCP Servers API — Docker MCP hub management."""

from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.schemas.mcp import MCPServerCreate, MCPServerResponse
from backend.services.mcp_service import list_servers, get_server, create_server
from backend.middleware.auth_middleware import get_current_user
from backend.mcp.docker_hub import DockerMCPHub

router = APIRouter(prefix="/mcp/servers", tags=["mcp-servers"])
docker_hub = DockerMCPHub()


@router.get("", response_model=list[MCPServerResponse])
async def list_all(db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    servers = await list_servers(db)
    return servers


@router.post("", response_model=MCPServerResponse, status_code=201)
async def create(data: MCPServerCreate, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    server = await create_server(db, data.model_dump())
    return MCPServerResponse(
        id=server.id,
        name=server.name,
        image=server.image,
        status=server.status,
        config=server.config,
        is_enabled=server.is_enabled,
        created_at=server.created_at,
    )


@router.post("/{server_id}/start")
async def start(server_id: UUID, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    server = await get_server(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    try:
        result = await docker_hub.start_server(server)
        server.status = "running"
        server.container_id = result.get("container_id")
        server.sse_url = result.get("sse_url")
        await db.flush()
        return {"status": "running", "container_id": result.get("container_id")}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{server_id}/stop")
async def stop(server_id: UUID, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    server = await get_server(db, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    try:
        await docker_hub.stop_server(server)
        server.status = "stopped"
        server.container_id = None
        await db.flush()
        return {"status": "stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
