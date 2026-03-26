"""Query Reformulation Service — resolve follow-up questions."""
from __future__ import annotations

from openai import AsyncOpenAI

from app.config import Settings
from app.models.session import ConversationTurn
from app.utils.logging import get_logger

logger = get_logger(__name__)

_REFORMULATION_PROMPT = """\
Given the conversation history below and a follow-up question, rewrite the \
follow-up into a self-contained standalone question that includes all necessary \
context. Do NOT answer the question — only reformulate it. If the follow-up is \
already standalone, return it unchanged.

Conversation history:
{history}

Follow-up question: {question}

Standalone question:"""


class QueryReformulator:

    def __init__(self, settings: Settings) -> None:
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        # Use a fast, cheap model for reformulation
        self._model = "gpt-4o-mini"

    async def reformulate(
        self,
        query: str,
        conversation_history: list[ConversationTurn],
    ) -> str:
        if not conversation_history:
            return query

        history_text = self._format_history(conversation_history)
        prompt = _REFORMULATION_PROMPT.format(history=history_text, question=query)

        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=256,
        )
        reformulated = response.choices[0].message.content or query
        return reformulated.strip()

    @staticmethod
    def _format_history(turns: list[ConversationTurn]) -> str:
        parts = []
        for turn in turns[-5:]:  # only send recent context to keep costs low
            parts.append(f"User: {turn.user_query}")
            parts.append(f"Assistant: {turn.assistant_response[:400]}")
        return "\n".join(parts)
