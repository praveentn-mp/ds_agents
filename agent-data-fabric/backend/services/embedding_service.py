"""Embedding service — sentence-transformers/all-MiniLM-L6-v2 for vector search."""

import asyncio
import logging
from typing import Optional

import numpy as np

logger = logging.getLogger("adf.embedding")

# Singleton model holder
_model = None
_model_lock = asyncio.Lock()

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_DIM = 384


def _load_model():
    """Load the sentence-transformer model (lazy, cached)."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        logger.info(f"Loading embedding model: {MODEL_NAME}")
        _model = SentenceTransformer(MODEL_NAME)
        logger.info("Embedding model loaded successfully")
    return _model


async def get_model():
    """Async-safe model getter with lock to avoid double-loading."""
    global _model
    if _model is not None:
        return _model
    async with _model_lock:
        if _model is not None:
            return _model
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _load_model)
        return _model


def embed_texts_sync(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts synchronously. Returns list of 384-dim vectors."""
    if not texts:
        return []
    model = _load_model()
    embeddings = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
    return embeddings.tolist()


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed a batch of texts asynchronously. Returns list of 384-dim vectors."""
    if not texts:
        return []
    await get_model()  # Ensure model is loaded
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, embed_texts_sync, texts)


async def embed_single(text: str) -> list[float]:
    """Embed a single text string. Returns 384-dim vector."""
    results = await embed_texts([text])
    return results[0] if results else [0.0] * EMBEDDING_DIM


def embed_single_sync(text: str) -> list[float]:
    """Embed a single text synchronously."""
    results = embed_texts_sync([text])
    return results[0] if results else [0.0] * EMBEDDING_DIM
