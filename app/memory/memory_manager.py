"""Memory Manager — orchestrates history read/write for RAGPipeline."""
from __future__ import annotations

import asyncio
from collections import defaultdict

from app.db.session_store import SessionStore
from app.memory.context_builder import ContextBuilder
from app.memory.memory_compressor import MemoryCompressor
from app.models.query import Citation
from app.models.session import ConversationTurn
from app.utils.logging import get_logger

logger = get_logger(__name__)


class MemoryManager:

    def __init__(
        self,
        session_store: SessionStore,
        context_builder: ContextBuilder,
        compressor: MemoryCompressor,
    ) -> None:
        self._store = session_store
        self._builder = context_builder
        self._compressor = compressor
        # Per-session lock prevents concurrent record_turn calls from racing
        # on the update→compress→replace sequence.
        self._session_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def get_formatted_history(
        self,
        session_id: str,
        token_budget: int = 1024,
    ) -> str:
        session = await self._store.get_session(session_id)
        if session is None or not session.conversation_history:
            return ""
        return self._builder.build(session.conversation_history, token_budget)

    async def record_turn(
        self,
        session_id: str,
        user_query: str,
        standalone_query: str,
        assistant_response: str,
        retrieved_chunk_ids: list[str],
        citations: list[Citation],
    ) -> None:
        turn = ConversationTurn(
            user_query=user_query,
            standalone_query=standalone_query,
            assistant_response=assistant_response,
            retrieved_chunk_ids=retrieved_chunk_ids,
            citations=citations,
        )
        async with self._session_locks[session_id]:
            session = await self._store.update_session(session_id, turn)
            if self._compressor.should_compress(session.turn_count):
                compressed = await self._compressor.compress(session.conversation_history)
                await self._store.replace_history(session_id, compressed)

    async def get_turn_count(self, session_id: str) -> int:
        session = await self._store.get_session(session_id)
        return session.turn_count if session else 0
