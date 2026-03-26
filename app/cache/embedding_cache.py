"""Embedding cache — sits in front of EmbedderService.embed_query()."""
from __future__ import annotations

import hashlib

from app.cache.cache_backend import CacheBackend
from app.services.embedder import EmbedderService
from app.utils.logging import get_logger

logger = get_logger(__name__)


class EmbeddingCache:

    def __init__(self, backend: CacheBackend, embedder: EmbedderService, ttl: int = 86400) -> None:
        self._backend = backend
        self._embedder = embedder
        self._ttl = ttl

    async def get_or_embed(self, query_text: str) -> list[float]:
        key = self._make_key(query_text)
        cached = await self._backend.get(key)
        if cached is not None:
            return cached

        vector = await self._embedder.embed_query(query_text)
        await self._backend.set(key, vector, ttl_seconds=self._ttl)
        return vector

    async def invalidate(self, query_text: str) -> None:
        key = self._make_key(query_text)
        await self._backend.delete(key)

    async def warm(self, queries: list[str]) -> None:
        for q in queries:
            await self.get_or_embed(q)

    @staticmethod
    def _make_key(query_text: str) -> str:
        normalized = query_text.strip().lower()
        return "emb:" + hashlib.sha256(normalized.encode()).hexdigest()
