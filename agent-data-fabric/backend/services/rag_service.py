"""RAG service — indexing and retrieval."""

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models.mcp_resource import MCPResource


async def index_resource(db: AsyncSession, resource_uri: str) -> dict:
    """Index a resource for RAG retrieval."""
    # Placeholder — full LlamaIndex integration
    return {"status": "indexed", "resource_uri": resource_uri}


async def search(db: AsyncSession, query: str, top_k: int = 5) -> list[dict]:
    """Semantic search across indexed resources."""
    # Placeholder — full pgvector search
    return []
