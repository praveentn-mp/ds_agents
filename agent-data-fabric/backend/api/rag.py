"""RAG API — index and search."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.services.rag_service import index_resource, search
from backend.middleware.auth_middleware import get_current_user
from pydantic import BaseModel

router = APIRouter(prefix="/rag", tags=["rag"])


class IndexRequest(BaseModel):
    resource_uri: str


class SearchRequest(BaseModel):
    query: str
    top_k: int = 5


@router.post("/index")
async def index(data: IndexRequest, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    return await index_resource(db, data.resource_uri)


@router.post("/search")
async def search_endpoint(data: SearchRequest, db: AsyncSession = Depends(get_db), user=Depends(get_current_user)):
    results = await search(db, data.query, data.top_k)
    return {"results": results}
