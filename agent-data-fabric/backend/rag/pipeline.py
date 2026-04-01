"""RAG pipeline — retrieve → augment → respond."""

from backend.rag.indexer import RAGIndexer
from backend.rag.retriever import RAGRetriever
from backend.config import settings


class RAGPipeline:
    """Full RAG pipeline: index, retrieve, augment, respond."""

    def __init__(self):
        self.indexer = RAGIndexer(settings.database_url_sync)
        self.retriever = RAGRetriever(settings.database_url_sync)

    async def index(self, source_uri: str, content: str, metadata: dict = None) -> dict:
        return await self.indexer.index_document(source_uri, content, metadata)

    async def query(self, question: str, top_k: int = 5) -> dict:
        chunks = await self.retriever.search(question, top_k)
        if not chunks:
            return {"answer": None, "sources": []}

        context = "\n\n".join([c["text"] for c in chunks])
        return {
            "context": context,
            "sources": chunks,
        }
