"""RAG indexer — chunk and embed documents into pgvector."""

import logging
from typing import Optional

logger = logging.getLogger("adf.rag.indexer")


class RAGIndexer:
    """Indexes documents into pgvector for semantic search."""

    def __init__(self, connection_string: str):
        self.connection_string = connection_string
        self._index = None

    async def index_document(self, source_uri: str, content: str, metadata: Optional[dict] = None) -> dict:
        """Chunk and embed a document, storing in pgvector."""
        try:
            from llama_index.core import Document, VectorStoreIndex
            from llama_index.vector_stores.postgres import PGVectorStore

            vector_store = PGVectorStore.from_params(
                connection_string=self.connection_string,
                table_name="rag_chunks",
                embed_dim=1536,
            )

            doc = Document(text=content, metadata=metadata or {"source_uri": source_uri})
            index = VectorStoreIndex.from_documents([doc], vector_store=vector_store)

            return {"status": "indexed", "source_uri": source_uri, "chunks": 1}
        except ImportError:
            logger.warning("LlamaIndex not fully configured. Storing as placeholder.")
            return {"status": "placeholder", "source_uri": source_uri}
        except Exception as e:
            logger.error(f"Indexing failed: {e}")
            return {"status": "error", "error": str(e)}
