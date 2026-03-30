"""Tests for ChunkerService — token-bounded splitting and metadata."""
from __future__ import annotations

import pytest

from app.config import Settings
from app.services.chunker import ChunkerService
from app.utils.token_counter import count_tokens


@pytest.fixture
def chunker(settings) -> ChunkerService:
    return ChunkerService(settings)


@pytest.fixture
def long_text() -> str:
    # ~1500 tokens of meaningful text
    paragraph = (
        "Artificial intelligence is transforming the way humans interact with technology. "
        "Machine learning algorithms can now recognise images, translate languages, and "
        "generate natural language text with remarkable accuracy. Deep neural networks, "
        "trained on vast datasets, have achieved superhuman performance on many benchmarks. "
        "Researchers continue to push the boundaries of what is possible, exploring new "
        "architectures and training methods. The field moves quickly, and practitioners "
        "must stay current to remain effective. Transfer learning has democratised AI "
        "by allowing smaller organisations to fine-tune large pre-trained models. "
        "Ethical considerations around bias, fairness, and transparency are increasingly "
        "important as AI systems are deployed in high-stakes domains such as healthcare, "
        "criminal justice, and financial services. Interpretability research aims to "
        "understand the internal representations learned by neural networks. "
    )
    return (paragraph * 5).strip()


@pytest.fixture
def short_text() -> str:
    return "This is a very short document with only a few words."


# ---------------------------------------------------------------------------
# Basic chunking
# ---------------------------------------------------------------------------

def test_chunk_sizes_within_budget(chunker, long_text):
    chunks = chunker.chunk(long_text, [0], "doc-1", "test.pdf")
    for c in chunks:
        assert c.token_count <= chunker._max_tokens


def test_empty_text_returns_empty_list(chunker):
    result = chunker.chunk("", [], "doc-1", "test.pdf")
    assert result == []


def test_whitespace_only_text_returns_empty_list(chunker):
    result = chunker.chunk("   \n\n  \t  ", [], "doc-1", "test.pdf")
    assert result == []


def test_short_document_produces_one_chunk(chunker, short_text):
    chunks = chunker.chunk(short_text, [0], "doc-1", "test.pdf")
    assert len(chunks) == 1
    assert chunks[0].text.strip() == short_text.strip()


def test_long_document_produces_multiple_chunks(chunker, long_text):
    chunks = chunker.chunk(long_text, [0], "doc-1", "test.pdf")
    assert len(chunks) > 1


# ---------------------------------------------------------------------------
# Chunk index ordering
# ---------------------------------------------------------------------------

def test_chunk_indices_are_sequential(chunker, long_text):
    chunks = chunker.chunk(long_text, [0], "doc-1", "test.pdf")
    for i, c in enumerate(chunks):
        assert c.chunk_index == i


# ---------------------------------------------------------------------------
# Metadata propagation
# ---------------------------------------------------------------------------

def test_document_id_on_all_chunks(chunker, long_text):
    chunks = chunker.chunk(long_text, [0], "doc-42", "test.pdf")
    for c in chunks:
        assert c.document_id == "doc-42"


def test_document_name_on_all_chunks(chunker, long_text):
    chunks = chunker.chunk(long_text, [0], "doc-1", "my_report.pdf")
    for c in chunks:
        assert c.document_name == "my_report.pdf"


def test_embedding_is_none_on_output(chunker, long_text):
    chunks = chunker.chunk(long_text, [0], "doc-1", "test.pdf")
    for c in chunks:
        assert c.embedding is None


def test_chunk_ids_are_unique(chunker, long_text):
    chunks = chunker.chunk(long_text, [0], "doc-1", "test.pdf")
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# Character offsets
# ---------------------------------------------------------------------------

def test_char_offsets_non_negative(chunker, long_text):
    chunks = chunker.chunk(long_text, [0], "doc-1", "test.pdf")
    for c in chunks:
        assert c.start_char_offset >= 0
        assert c.end_char_offset > c.start_char_offset


def test_first_chunk_starts_at_zero(chunker, long_text):
    chunks = chunker.chunk(long_text, [0], "doc-1", "test.pdf")
    assert chunks[0].start_char_offset == 0


# ---------------------------------------------------------------------------
# Page number tracking
# ---------------------------------------------------------------------------

def test_single_page_all_chunks_on_page_1(chunker, long_text):
    chunks = chunker.chunk(long_text, [0], "doc-1", "test.pdf")
    for c in chunks:
        assert 1 in c.page_numbers


def test_multi_page_boundary_offsets(chunker):
    page1 = "First page content. " * 20
    page2 = "Second page content. " * 20
    text = page1 + "\n" + page2
    offsets = [0, len(page1) + 1]

    chunks = chunker.chunk(text, offsets, "doc-1", "test.pdf")
    # At least the first chunk should be on page 1
    assert any(1 in c.page_numbers for c in chunks)
    # At least one chunk should be on page 2
    assert any(2 in c.page_numbers for c in chunks)


# ---------------------------------------------------------------------------
# Token count accuracy
# ---------------------------------------------------------------------------

def test_token_count_matches_actual(chunker, short_text):
    chunks = chunker.chunk(short_text, [0], "doc-1", "test.pdf")
    assert len(chunks) == 1
    assert chunks[0].token_count == count_tokens(chunks[0].text)


# ---------------------------------------------------------------------------
# Overlap behaviour
# ---------------------------------------------------------------------------

def test_overlap_creates_shared_content(chunker, long_text):
    chunks = chunker.chunk(long_text, [0], "doc-1", "test.pdf")
    if len(chunks) < 2:
        pytest.skip("Need at least two chunks to test overlap")
    # The end of chunk[0] should share tokens with the start of chunk[1]
    # (verified by checking char offsets are not strictly sequential)
    assert chunks[1].start_char_offset < chunks[0].end_char_offset
