"""Query Reformulation Service — resolve follow-up questions."""
from __future__ import annotations

from app.config import Settings
from app.models.session import ConversationTurn
from app.utils.openai_client import make_openai_client
from app.utils.logging import get_logger

logger = get_logger(__name__)

_REFORMULATION_PROMPT = """\
You are preparing a question for semantic search over a document.

Given the conversation history and a follow-up question, produce a single \
standalone search query that:
1. Resolves any pronouns or references using the conversation history.
2. Expands vague or inferential phrasing into concrete, document-searchable \
   terms. For example:
   - "Is he a bad guy?" → "professional misconduct unethical behaviour criminal record character flaws"
   - "Is she a good hire?" → "qualifications skills experience achievements suitability"
   - "Should I trust this?" → "credibility reliability accuracy limitations caveats"
3. Keeps the query concise (≤ 25 words).
4. Does NOT answer the question — only reformulates it for retrieval.

If the follow-up is already a concrete, standalone question, return it unchanged.

Conversation history:
{history}

Follow-up question: {question}

Standalone search query:"""


class QueryReformulator:

    def __init__(self, settings: Settings) -> None:
        self._client = make_openai_client(settings)
        # Use a fast, cheap model for reformulation
        self._model = "gpt-4o-mini"

    async def reformulate(
        self,
        query: str,
        conversation_history: list[ConversationTurn],
    ) -> str:
        # Always reformulate — even on first turn — to expand inferential queries
        history_text = self._format_history(conversation_history) if conversation_history else "(none)"
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
