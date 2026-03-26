"""Chunk domain model."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field


@dataclass
class Chunk:
    document_id: str
    document_name: str
    chunk_index: int
    text: str
    token_count: int
    page_numbers: list[int]
    start_char_offset: int
    end_char_offset: int
    chunk_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    embedding: list[float] | None = None

    @property
    def metadata(self) -> dict:
        """Dict representation stored in vector DB alongside the vector."""
        return {
            "chunk_id": self.chunk_id,
            "document_id": self.document_id,
            "document_name": self.document_name,
            "chunk_index": self.chunk_index,
            "page_numbers": self.page_numbers,
            "token_count": self.token_count,
            "text": self.text,
        }
