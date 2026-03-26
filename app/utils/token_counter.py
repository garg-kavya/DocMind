"""Token counting utilities using tiktoken."""
from __future__ import annotations

import tiktoken

_ENCODING: tiktoken.Encoding | None = None


def _get_encoding() -> tiktoken.Encoding:
    global _ENCODING
    if _ENCODING is None:
        _ENCODING = tiktoken.get_encoding("cl100k_base")
    return _ENCODING


def count_tokens(text: str, model: str = "cl100k_base") -> int:
    """Count tokens in *text* using the cl100k_base encoding."""
    enc = _get_encoding()
    return len(enc.encode(text))


def truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Truncate *text* so it fits within *max_tokens* tokens."""
    enc = _get_encoding()
    tokens = enc.encode(text)
    if len(tokens) <= max_tokens:
        return text
    return enc.decode(tokens[:max_tokens])


def estimate_chunk_count(text: str, chunk_size: int, overlap: int) -> int:
    """Estimate number of chunks for a document."""
    total = count_tokens(text)
    if total <= chunk_size:
        return 1
    step = chunk_size - overlap
    return max(1, (total - overlap + step - 1) // step)
