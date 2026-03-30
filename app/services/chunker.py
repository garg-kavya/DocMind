"""Document Chunking Service — semantic, structure-aware splitting."""
from __future__ import annotations

import bisect
import re
import uuid

import tiktoken as _tiktoken

from app.config import Settings
from app.models.chunk import Chunk
from app.utils.token_counter import count_tokens

_ENC = _tiktoken.get_encoding("cl100k_base")

# Paragraph boundary: two or more blank lines / whitespace-only lines
_PARA_SEP = re.compile(r"\n[ \t]*\n")

# Sentence boundary: period / ! / ? followed by whitespace (lookbehind keeps the punct)
_SENT_SEP = re.compile(r"(?<=[.!?])\s+")

# A small buffer so that (overlap_tokens + sep_tokens + group_tokens) ≤ max_tokens.
# "\n\n" costs at most 2–3 tokens; 5 gives comfortable headroom.
_SEP_MARGIN = 5


class ChunkerService:
    """Split cleaned document text into semantically coherent, token-bounded chunks.

    Splitting priority:
    1. Paragraph boundaries  (double newline — respects section breaks)
    2. Sentence boundaries   (for paragraphs that exceed the token budget)
    3. Token-based hard cut  (last resort — run-on content or OCR output)

    Overlap is implemented by prepending the tail tokens of the previous
    chunk to the next chunk, ensuring retrieval continuity at boundaries.
    Token budget is enforced on actual tiktoken counts (not estimates).
    """

    def __init__(self, settings: Settings) -> None:
        self._max_tokens = settings.chunk_size_tokens
        self._overlap = settings.chunk_overlap_tokens
        # Budget for a sentence group BEFORE overlap is prepended.
        # Guarantees: overlap + sep + group ≤ max_tokens.
        self._group_budget = max(1, self._max_tokens - self._overlap - _SEP_MARGIN)

    # ------------------------------------------------------------------
    # Public interface (unchanged signature)
    # ------------------------------------------------------------------

    def chunk(
        self,
        cleaned_text: str,
        page_boundary_offsets: list[int],
        document_id: str,
        document_name: str,
    ) -> list[Chunk]:
        """Return a list of Chunks with page numbers and char offsets."""
        if not cleaned_text.strip():
            return []

        raw = self._build_raw_chunks(cleaned_text)
        result = []
        for idx, (text, start, end) in enumerate(raw):
            pages = self._page_numbers(start, end, page_boundary_offsets)
            result.append(
                Chunk(
                    document_id=document_id,
                    document_name=document_name,
                    chunk_index=idx,
                    text=text,
                    token_count=count_tokens(text),
                    page_numbers=pages,
                    start_char_offset=start,
                    end_char_offset=end,
                    chunk_id=str(uuid.uuid4()),
                )
            )
        return result

    # ------------------------------------------------------------------
    # Stage 1 — split into semantic segments
    # ------------------------------------------------------------------

    def _build_raw_chunks(self, text: str) -> list[tuple[str, int, int]]:
        segments = self._split_into_segments(text)
        return self._group_with_overlap(segments)

    def _split_into_segments(self, text: str) -> list[tuple[str, int, int]]:
        """Split at paragraph boundaries; sub-split oversized paragraphs."""
        raw_segs: list[tuple[str, int, int]] = []
        prev = 0
        for match in _PARA_SEP.finditer(text):
            self._collect(text, prev, match.start(), raw_segs)
            prev = match.end()
        self._collect(text, prev, len(text), raw_segs)

        result: list[tuple[str, int, int]] = []
        for seg_text, seg_start, seg_end in raw_segs:
            if count_tokens(seg_text) > self._group_budget:
                result.extend(self._split_by_sentences(seg_text, seg_start))
            else:
                result.append((seg_text, seg_start, seg_end))
        return result

    @staticmethod
    def _collect(
        text: str, raw_start: int, raw_end: int, out: list[tuple[str, int, int]]
    ) -> None:
        """Strip a slice of *text* and append (stripped, start, end) to *out*."""
        raw = text[raw_start:raw_end]
        stripped = raw.strip()
        if not stripped:
            return
        leading = len(raw) - len(raw.lstrip())
        start = raw_start + leading
        end = start + len(stripped)
        out.append((stripped, start, end))

    def _split_by_sentences(
        self, text: str, base_offset: int
    ) -> list[tuple[str, int, int]]:
        """Group sentences up to *_group_budget* tokens; hard-split anything larger."""
        # Collect sentence spans within *text*
        spans: list[tuple[str, int, int]] = []
        prev = 0
        for m in _SENT_SEP.finditer(text):
            if prev < m.start():
                spans.append((text[prev : m.start()], prev, m.start()))
            prev = m.end()
        if prev < len(text):
            spans.append((text[prev:], prev, len(text)))

        result: list[tuple[str, int, int]] = []
        acc: list[tuple[str, int, int]] = []
        acc_start = acc_end = 0
        acc_tokens = 0

        for sent, s_start, s_end in spans:
            st = count_tokens(sent)
            if acc_tokens + st > self._group_budget and acc:
                combined = " ".join(t for t, _, _ in acc)
                result.append((combined, base_offset + acc_start, base_offset + acc_end))
                acc = [(sent, s_start, s_end)]
                acc_start, acc_end = s_start, s_end
                acc_tokens = st
            else:
                if not acc:
                    acc_start = s_start
                acc.append((sent, s_start, s_end))
                acc_end = s_end
                acc_tokens += st

        if acc:
            combined = " ".join(t for t, _, _ in acc)
            result.append((combined, base_offset + acc_start, base_offset + acc_end))

        # Hard fallback for individual sentences that are still over budget
        final: list[tuple[str, int, int]] = []
        for seg_text, seg_start, seg_end in result:
            if count_tokens(seg_text) > self._max_tokens:
                final.extend(self._token_split(seg_text, seg_start))
            else:
                final.append((seg_text, seg_start, seg_end))
        return final

    def _token_split(
        self, text: str, base_offset: int
    ) -> list[tuple[str, int, int]]:
        """Hard token-based split — last resort for run-on OCR text."""
        tokens = _enc_encode(text)
        step = max(1, self._max_tokens - self._overlap)
        result: list[tuple[str, int, int]] = []
        pos = 0
        while pos < len(tokens):
            end = min(pos + self._max_tokens, len(tokens))
            chunk_text = _enc_decode(tokens[pos:end])
            c_start = base_offset + _tok_to_char(tokens, pos, text)
            c_end = base_offset + _tok_to_char(tokens, end, text)
            result.append((chunk_text, c_start, c_end))
            if end == len(tokens):
                break
            pos += step
        return result

    # ------------------------------------------------------------------
    # Stage 2 — group segments and apply overlap
    # ------------------------------------------------------------------

    def _group_with_overlap(
        self, segments: list[tuple[str, int, int]]
    ) -> list[tuple[str, int, int]]:
        """Merge small segments up to the token budget; prepend tail overlap."""
        if not segments:
            return []

        chunks: list[tuple[str, int, int]] = []
        acc_texts: list[str] = []
        acc_start: int | None = None
        acc_end: int = 0

        for seg_text, seg_start, seg_end in segments:
            # Test actual token count of potential merged chunk
            candidate_texts = acc_texts + [seg_text]
            candidate_text = "\n\n".join(candidate_texts)
            candidate_tokens = count_tokens(candidate_text)

            if candidate_tokens > self._max_tokens and acc_texts:
                # Emit the accumulated chunk
                chunk_text = "\n\n".join(acc_texts)
                chunks.append((chunk_text, acc_start, acc_end))  # type: ignore[arg-type]

                # Prepend overlap from the emitted chunk into the next chunk
                overlap_str, overlap_start = self._tail_overlap(
                    chunk_text, acc_start, acc_end  # type: ignore[arg-type]
                )
                if overlap_str:
                    ov_candidate = overlap_str + "\n\n" + seg_text
                    if count_tokens(ov_candidate) <= self._max_tokens:
                        acc_texts = [overlap_str, seg_text]
                        acc_start = overlap_start
                        acc_end = seg_end
                        continue

                # No room for overlap (seg is large) — just start fresh
                acc_texts = [seg_text]
                acc_start = seg_start
                acc_end = seg_end
            else:
                if not acc_texts:
                    acc_start = seg_start
                acc_texts = candidate_texts
                acc_end = seg_end

        if acc_texts:
            chunk_text = "\n\n".join(acc_texts)
            chunks.append((chunk_text, acc_start, acc_end))  # type: ignore[arg-type]

        return chunks

    def _tail_overlap(
        self, text: str, text_start: int, text_end: int
    ) -> tuple[str, int]:
        """Return (last overlap_tokens of *text*, char offset in original).

        Returns ("", text_start) when the text is shorter than the overlap.
        """
        tokens = _enc_encode(text)
        if len(tokens) <= self._overlap:
            return "", text_start
        non_overlap = _enc_decode(tokens[: -self._overlap])
        overlap_str = _enc_decode(tokens[-self._overlap :])
        overlap_char_start = text_start + len(non_overlap)
        return overlap_str, overlap_char_start

    # ------------------------------------------------------------------
    # Page number mapping
    # ------------------------------------------------------------------

    @staticmethod
    def _page_numbers(
        start: int, end: int, page_boundary_offsets: list[int]
    ) -> list[int]:
        if not page_boundary_offsets:
            return [1]
        first = max(0, bisect.bisect_right(page_boundary_offsets, start) - 1)
        last = max(0, bisect.bisect_right(page_boundary_offsets, max(end - 1, start)) - 1)
        return list(range(first + 1, last + 2))


# ---------------------------------------------------------------------------
# Tiktoken helpers
# ---------------------------------------------------------------------------

def _enc_encode(text: str) -> list[int]:
    return _ENC.encode(text)


def _enc_decode(token_ids: list[int]) -> str:
    return _ENC.decode(token_ids)


def _tok_to_char(tokens: list[int], pos: int, text: str) -> int:
    if pos == 0:
        return 0
    return len(_ENC.decode(tokens[:pos]))
