"""Embedding Service — generate OpenAI vector embeddings."""
from __future__ import annotations

import asyncio

from openai import AsyncOpenAI

from app.config import Settings
from app.exceptions import EmbeddingAPIError, EmbeddingTimeoutError
from app.models.chunk import Chunk
from app.utils.logging import get_logger

logger = get_logger(__name__)


class EmbedderService:
    """Generate embeddings via the OpenAI Embeddings API."""

    def __init__(self, settings: Settings) -> None:
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = settings.embedding_model
        self._batch_size = settings.embedding_batch_size
        self._dimensions = settings.embedding_dimensions

    async def embed_chunks(self, chunks: list[Chunk]) -> list[Chunk]:
        """Batch-embed all chunks and populate chunk.embedding in-place."""
        if not chunks:
            return chunks

        batches = [
            chunks[i : i + self._batch_size]
            for i in range(0, len(chunks), self._batch_size)
        ]

        for batch in batches:
            texts = [c.text for c in batch]
            vectors = await self._embed_texts(texts)
            for chunk, vector in zip(batch, vectors):
                chunk.embedding = vector

        logger.info("Embedded %d chunks", len(chunks))
        return chunks

    async def embed_query(self, query_text: str) -> list[float]:
        """Embed a single query string. Called only by EmbeddingCache on miss."""
        vectors = await self._embed_texts([query_text])
        return vectors[0]

    async def _embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Call the OpenAI Embeddings API with retry on timeout."""
        for attempt in range(3):
            try:
                response = await self._client.embeddings.create(
                    model=self._model,
                    input=texts,
                )
                return [item.embedding for item in response.data]
            except asyncio.TimeoutError as exc:
                if attempt == 2:
                    raise EmbeddingTimeoutError("Embedding API timed out.") from exc
                await asyncio.sleep(2 ** attempt)
            except Exception as exc:
                raise EmbeddingAPIError(
                    f"Embedding API error: {exc}", detail=str(exc)
                ) from exc
        raise EmbeddingAPIError("Embedding failed after retries.")
