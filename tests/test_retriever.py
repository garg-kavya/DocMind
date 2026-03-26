"""Tests for RetrieverService — vector search, threshold, and MMR."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock

from app.config import Settings
from app.exceptions import NoDocumentsError, StorageReadError
from app.models.chunk import Chunk
from app.models.query import ScoredChunk
from app.services.retriever import RetrieverService


def _make_chunk(document_id: str = "doc-1", index: int = 0, text: str = "test") -> Chunk:
    return Chunk(
        document_id=document_id,
        document_name="test.pdf",
        chunk_index=index,
        text=text,
        token_count=5,
        page_numbers=[1],
        start_char_offset=index * 100,
        end_char_offset=(index + 1) * 100,
    )


def _scored(chunk: Chunk, score: float) -> tuple[Chunk, float]:
    return (chunk, score)


@pytest.fixture
def mock_store():
    store = AsyncMock()
    return store


@pytest.fixture
def retriever(settings, mock_store) -> RetrieverService:
    return RetrieverService(mock_store, settings)


QUERY_EMBEDDING = [0.1] * 1536


# ---------------------------------------------------------------------------
# No documents guard
# ---------------------------------------------------------------------------

async def test_retrieve_raises_on_empty_document_ids(retriever):
    with pytest.raises(NoDocumentsError):
        await retriever.retrieve(QUERY_EMBEDDING, document_ids=[])


# ---------------------------------------------------------------------------
# Basic retrieval
# ---------------------------------------------------------------------------

async def test_retrieve_returns_scored_chunks(retriever, mock_store):
    chunks = [_make_chunk(index=i) for i in range(3)]
    mock_store.search = AsyncMock(
        return_value=[_scored(c, 0.90 - i * 0.05) for i, c in enumerate(chunks)]
    )

    result, meta = await retriever.retrieve(QUERY_EMBEDDING, document_ids=["doc-1"])

    assert len(result) == 3
    assert all(isinstance(sc, ScoredChunk) for sc in result)


async def test_retrieve_sets_bi_encoder_score(retriever, mock_store):
    chunk = _make_chunk()
    mock_store.search = AsyncMock(return_value=[_scored(chunk, 0.85)])

    result, _ = await retriever.retrieve(QUERY_EMBEDDING, document_ids=["doc-1"])

    assert result[0].bi_encoder_score == result[0].similarity_score


async def test_retrieve_metadata_populated(retriever, mock_store):
    chunks = [_make_chunk(index=i) for i in range(5)]
    mock_store.search = AsyncMock(
        return_value=[_scored(c, 0.92 - i * 0.03) for i, c in enumerate(chunks)]
    )

    _, meta = await retriever.retrieve(QUERY_EMBEDDING, document_ids=["doc-1"])

    assert meta.candidates_considered == 5
    assert meta.retrieval_time_ms >= 0
    assert meta.top_k_requested == retriever._top_k


# ---------------------------------------------------------------------------
# Threshold filtering
# ---------------------------------------------------------------------------

async def test_threshold_filters_low_scores(settings, mock_store):
    # Use a fixed threshold (0.70) independent of .env
    fixed = Settings(similarity_threshold=0.70)
    r = RetrieverService(mock_store, fixed)
    chunks = [_make_chunk(index=i) for i in range(5)]
    # Only first 2 are above 0.70
    scores = [0.95, 0.80, 0.65, 0.50, 0.40]
    mock_store.search = AsyncMock(
        return_value=[_scored(c, s) for c, s in zip(chunks, scores)]
    )

    result, meta = await r.retrieve(QUERY_EMBEDDING, document_ids=["doc-1"])

    assert len(result) == 2
    assert meta.candidates_after_threshold == 2
    assert all(sc.similarity_score >= r._threshold for sc in result)


async def test_threshold_all_filtered_returns_empty(settings, mock_store):
    # Use a fixed threshold (0.70) independent of .env
    fixed = Settings(similarity_threshold=0.70)
    r = RetrieverService(mock_store, fixed)
    chunks = [_make_chunk(index=i) for i in range(3)]
    mock_store.search = AsyncMock(
        return_value=[_scored(c, 0.30) for c in chunks]
    )

    result, _ = await r.retrieve(QUERY_EMBEDDING, document_ids=["doc-1"])

    assert result == []


# ---------------------------------------------------------------------------
# Vector store error
# ---------------------------------------------------------------------------

async def test_retrieve_wraps_store_error(retriever, mock_store):
    mock_store.search = AsyncMock(side_effect=RuntimeError("index error"))

    with pytest.raises(StorageReadError):
        await retriever.retrieve(QUERY_EMBEDDING, document_ids=["doc-1"])


# ---------------------------------------------------------------------------
# MMR diversity
# ---------------------------------------------------------------------------

def test_mmr_returns_top_k_from_candidates(retriever):
    candidates = [
        ScoredChunk(chunk=_make_chunk(index=i), similarity_score=0.9 - i * 0.05,
                    bi_encoder_score=0.9 - i * 0.05)
        for i in range(8)
    ]
    result = retriever.apply_mmr(candidates, top_k=3)

    assert len(result) == 3


def test_mmr_assigns_ranks(retriever):
    candidates = [
        ScoredChunk(chunk=_make_chunk(index=i), similarity_score=0.9 - i * 0.05,
                    bi_encoder_score=0.9 - i * 0.05)
        for i in range(5)
    ]
    result = retriever.apply_mmr(candidates, top_k=3)

    ranks = [sc.rank for sc in result]
    assert sorted(ranks) == list(range(1, len(result) + 1))


def test_mmr_fewer_candidates_than_k_returns_all(retriever):
    candidates = [
        ScoredChunk(chunk=_make_chunk(index=i), similarity_score=0.9,
                    bi_encoder_score=0.9)
        for i in range(2)
    ]
    result = retriever.apply_mmr(candidates, top_k=5)

    assert len(result) == 2


def test_mmr_first_selected_is_highest_score(retriever):
    candidates = [
        ScoredChunk(chunk=_make_chunk(index=i), similarity_score=0.5 + i * 0.1,
                    bi_encoder_score=0.5 + i * 0.1)
        for i in range(5)
    ]
    result = retriever.apply_mmr(candidates, top_k=3)

    # The highest-scoring candidate (last one, score=0.9) should be first
    assert result[0].similarity_score == max(c.similarity_score for c in candidates)


def test_mmr_empty_candidates_returns_empty(retriever):
    result = retriever.apply_mmr([], top_k=5)
    assert result == []
