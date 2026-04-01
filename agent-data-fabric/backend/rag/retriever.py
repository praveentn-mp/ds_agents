"""RAG retriever — semantic search over pgvector."""

import logging
from typing import Optional

logger = logging.getLogger("adf.rag.retriever")


class RAGRetriever:
    """Retrieves relevant chunks from pgvector."""

    def __init__(self, connection_string: str):
        self.connection_string = connection_string

    async def search(self, query: str, top_k: int = 5) -> list[dict]:
        """Semantic search across indexed documents."""
        try:
            from llama_index.core import VectorStoreIndex
            from llama_index.vector_stores.postgres import PGVectorStore

            vector_store = PGVectorStore.from_params(
                connection_string=self.connection_string,
                table_name="rag_chunks",
                embed_dim=1536,
            )

            index = VectorStoreIndex.from_vector_store(vector_store)
            retriever = index.as_retriever(similarity_top_k=top_k)
            nodes = retriever.retrieve(query)

            return [
                {
                    "text": node.text,
                    "score": node.score,
                    "metadata": node.metadata,
                }
                for node in nodes
            ]
        except ImportError:
            logger.warning("LlamaIndex not fully configured.")
            return []
        except Exception as e:
            logger.error(f"Retrieval failed: {e}")
            return []
