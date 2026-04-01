"""Health check endpoint."""

import asyncpg
from fastapi import APIRouter
from backend.config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    services = {"backend": "up"}

    # Check Postgres
    try:
        conn = await asyncpg.connect(
            host=settings.postgres_host,
            port=settings.postgres_port,
            database=settings.postgres_db,
            user=settings.postgres_user,
            password=settings.postgres_password,
        )
        await conn.fetchval("SELECT 1")
        await conn.close()
        services["postgres"] = "up"
    except Exception as e:
        services["postgres"] = f"down: {str(e)[:100]}"

    status = "healthy" if all(v == "up" for v in services.values()) else "degraded"
    return {"status": status, "services": services}
