"""Response cache — caches full GeneratedAnswer for 60s."""
from __future__ import annotations

import hashlib
import pickle
from typing import Awaitable, Callable

from app.cache.cache_backend import CacheBackend
from app.models.query import GeneratedAnswer
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ResponseCache:

    def __init__(self, backend: CacheBackend, ttl: int = 60) -> None:
        self._backend = backend
        self._ttl = ttl

    async def get_or_generate(
        self,
        query_text: str,
        session_id: str,
        document_ids: list[str],
        turn_count: int,
        generate_fn: Callable[[], Awaitable[GeneratedAnswer]],
    ) -> GeneratedAnswer:
        key = self._make_key(query_text, session_id, document_ids, turn_count)
        cached_bytes = await self._backend.get(key)
        if cached_bytes is not None:
            try:
                answer: GeneratedAnswer = pickle.loads(cached_bytes)
                answer.cache_hit = True
                answer.pipeline_metadata.response_cache_hit = True
                return answer
            except Exception:
                pass  # corrupt cache entry; fall through

        answer = await generate_fn()
        try:
            await self._backend.set(key, pickle.dumps(answer), ttl_seconds=self._ttl)
        except Exception as exc:
            logger.warning("Response cache write failed: %s", exc)

        return answer

    async def invalidate_session(self, session_id: str) -> None:
        # InMemoryCache doesn't expose prefix-scan; clear is heavy so we skip
        # In Redis this would be: SCAN for keys containing session_id
        pass

    async def invalidate_by_document(self, document_id: str) -> None:
        # Same limitation as above; acceptable given short 60s TTL
        pass

    async def get_stats(self) -> dict:
        return await self._backend.stats()

    @staticmethod
    def _make_key(
        query_text: str,
        session_id: str,
        document_ids: list[str],
        turn_count: int,
    ) -> str:
        raw = (
            session_id
            + "|" + query_text.strip().lower()
            + "|" + ",".join(sorted(document_ids))
            + "|" + str(turn_count)
        )
        return "resp:" + hashlib.sha256(raw.encode()).hexdigest()
