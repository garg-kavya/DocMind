"""Context Builder — token-budgeted history formatter."""
from __future__ import annotations

from app.models.session import ConversationTurn
from app.utils.token_counter import count_tokens


class ContextBuilder:

    def build(self, turns: list[ConversationTurn], token_budget: int = 1024) -> str:
        """Return a formatted history string that fits within *token_budget* tokens.

        Iterates newest → oldest; returns oldest-first so the LLM reads
        history in chronological order.
        """
        if not turns:
            return ""

        included: list[str] = []
        used = 0

        for turn in reversed(turns):
            if turn.is_summary and turn.summary_text:
                text = f"Summary of earlier conversation:\n{turn.summary_text}"
            else:
                text = f"User: {turn.user_query}\nAssistant: {turn.assistant_response}"

            tokens = count_tokens(text)
            if used + tokens > token_budget:
                break
            included.append(text)
            used += tokens

        included.reverse()  # restore chronological order
        return "\n\n".join(included)

    def estimate_tokens(self, turns: list[ConversationTurn]) -> int:
        total = 0
        for turn in turns:
            text = f"User: {turn.user_query}\nAssistant: {turn.assistant_response}"
            total += count_tokens(text)
        return total
