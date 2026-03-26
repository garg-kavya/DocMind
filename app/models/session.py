"""Session and ConversationTurn domain models."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.query import Citation


@dataclass
class ConversationTurn:
    user_query: str
    standalone_query: str
    assistant_response: str
    retrieved_chunk_ids: list[str]
    citations: list["Citation"] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    is_summary: bool = False
    summary_text: str | None = None
    turns_covered: int = 0


@dataclass
class Session:
    document_ids: list[str]
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    conversation_history: list[ConversationTurn] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_active_at: datetime = field(default_factory=datetime.utcnow)
    config_overrides: dict | None = None

    @property
    def turn_count(self) -> int:
        return len(self.conversation_history)
