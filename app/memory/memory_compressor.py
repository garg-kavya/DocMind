"""Memory Compressor — summarise old turns to keep history bounded."""
from __future__ import annotations

from app.config import Settings
from app.models.session import ConversationTurn
from app.utils.openai_client import make_openai_client
from app.utils.logging import get_logger

logger = get_logger(__name__)

_SUMMARIZE_PROMPT = """\
Summarize the following conversation concisely, preserving all key facts \
and decisions mentioned. Write in third person.

Conversation:
{transcript}

Summary:"""


class MemoryCompressor:

    def __init__(self, settings: Settings) -> None:
        self._client = make_openai_client(settings)
        self._threshold = settings.compression_threshold
        self._n_compress = settings.compression_turns

    def should_compress(self, turn_count: int) -> bool:
        return turn_count >= self._threshold

    async def compress(
        self,
        turns: list[ConversationTurn],
        n_turns_to_compress: int | None = None,
    ) -> list[ConversationTurn]:
        n = n_turns_to_compress or self._n_compress
        if len(turns) <= n:
            return turns

        to_compress = turns[:n]
        remaining = turns[n:]

        transcript = "\n".join(
            f"User: {t.user_query}\nAssistant: {t.assistant_response}"
            for t in to_compress
        )
        prompt = _SUMMARIZE_PROMPT.format(transcript=transcript)

        try:
            response = await self._client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=300,
            )
            summary_text = response.choices[0].message.content or ""
        except Exception as exc:
            logger.warning("Memory compression failed: %s; keeping raw turns", exc)
            return turns

        summary_turn = ConversationTurn(
            user_query="",
            standalone_query="",
            assistant_response="",
            retrieved_chunk_ids=[],
            is_summary=True,
            summary_text=summary_text.strip(),
            turns_covered=n,
        )
        logger.info("Compressed %d turns into summary", n)
        return [summary_turn] + remaining
