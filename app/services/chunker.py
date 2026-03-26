"""Document Chunking Service — split text into token-bounded chunks."""
from __future__ import annotations

import bisect
import uuid

from app.config import Settings
from app.models.chunk import Chunk
from app.utils.token_counter import count_tokens


class ChunkerService:
    """Split cleaned document text into overlapping token-bounded chunks."""

    def __init__(self, settings: Settings) -> None:
        self._chunk_size = settings.chunk_size_tokens
        self._overlap = settings.chunk_overlap_tokens
        self._separators = settings.split_separators

    def chunk(
        self,
        cleaned_text: str,
        page_boundary_offsets: list[int],
        document_id: str,
        document_name: str,
    ) -> list[Chunk]:
        """Split *cleaned_text* into chunks; assign page numbers via offsets."""
        if not cleaned_text.strip():
            return []

        raw_chunks = self._recursive_split(cleaned_text, self._separators)
        chunks: list[Chunk] = []

        for idx, (text, start, end) in enumerate(raw_chunks):
            page_numbers = self._page_numbers_for_range(
                start, end, page_boundary_offsets
            )
            chunks.append(
                Chunk(
                    document_id=document_id,
                    document_name=document_name,
                    chunk_index=idx,
                    text=text,
                    token_count=count_tokens(text),
                    page_numbers=page_numbers,
                    start_char_offset=start,
                    end_char_offset=end,
                    chunk_id=str(uuid.uuid4()),
                )
            )

        return chunks

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _recursive_split(
        self,
        text: str,
        separators: list[str],
    ) -> list[tuple[str, int, int]]:
        """Return list of (chunk_text, start_char, end_char) with overlap."""
        # Tokenise the full text once
        tokens = _tokenize(text)
        total = len(tokens)

        if total == 0:
            return []

        results: list[tuple[str, int, int]] = []
        step = max(1, self._chunk_size - self._overlap)
        pos = 0

        while pos < total:
            end = min(pos + self._chunk_size, total)
            chunk_tokens = tokens[pos:end]
            chunk_text = _decode(chunk_tokens)

            # Char offsets: find the text in the original
            # (approximation via cumulative char lengths)
            char_start = _token_to_char(tokens, pos, text)
            char_end = _token_to_char(tokens, end, text)

            results.append((chunk_text, char_start, char_end))
            if end == total:
                break
            pos += step

        return results

    @staticmethod
    def _page_numbers_for_range(
        start: int,
        end: int,
        page_boundary_offsets: list[int],
    ) -> list[int]:
        """Return 1-based page numbers the char range [start, end) spans."""
        if not page_boundary_offsets:
            return [1]

        # Find first page whose boundary is <= start
        first_page = bisect.bisect_right(page_boundary_offsets, start) - 1
        # Find last page whose boundary is < end
        last_page = bisect.bisect_right(page_boundary_offsets, end - 1) - 1

        first_page = max(0, first_page)
        last_page = max(0, last_page)

        return list(range(first_page + 1, last_page + 2))  # 1-based


# ---------------------------------------------------------------------------
# Tiktoken helpers (cached at module level)
# ---------------------------------------------------------------------------

import tiktoken as _tiktoken  # noqa: E402

_ENC = _tiktoken.get_encoding("cl100k_base")


def _tokenize(text: str) -> list[int]:
    return _ENC.encode(text)


def _decode(token_ids: list[int]) -> str:
    return _ENC.decode(token_ids)


def _token_to_char(tokens: list[int], token_pos: int, original: str) -> int:
    """Approximate char offset of token position by decoding prefix."""
    if token_pos == 0:
        return 0
    prefix = _ENC.decode(tokens[:token_pos])
    return len(prefix)
