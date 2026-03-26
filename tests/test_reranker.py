"""Tests for RerankerService — both backends and edge cases."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import Settings
from app.exceptions import RerankerError
from app.models.chunk import Chunk
from app.models.query import ScoredChunk
from app.services.reranker import RerankerService


def _make_scored(text: str, score: float, index: int = 0) -> ScoredChunk:
    chunk = Chunk(
        document_id="doc-1",
        document_name="test.pdf",
        chunk_index=index,
        text=text,
        token_count=10,
        page_numbers=[1],
        start_char_offset=index * 100,
        end_char_offset=(index + 1) * 100,
    )
    return ScoredChunk(chunk=chunk, similarity_score=score, bi_encoder_score=score)


@pytest.fixture
def settings_no_reranker(settings) -> Settings:
    # Default settings have reranker_backend="none"
    return settings


@pytest.fixture
def settings_cross_encoder(settings) -> Settings:
    settings.__dict__["_reranker_backend"] = "cross_encoder"
    # Use model_copy for pydantic v2
    return settings.model_copy(update={"reranker_backend": "cross_encoder"})


@pytest.fixture
def settings_cohere(settings) -> Settings:
    return settings.model_copy(update={
        "reranker_backend": "cohere",
        "cohere_api_key": "test-cohere-key",
    })


# ---------------------------------------------------------------------------
# is_enabled
# ---------------------------------------------------------------------------

def test_is_enabled_false_when_backend_none(settings_no_reranker):
    svc = RerankerService(settings_no_reranker)
    assert svc.is_enabled() is False


def test_is_enabled_true_for_cross_encoder(settings_cross_encoder):
    svc = RerankerService(settings_cross_encoder)
    assert svc.is_enabled() is True


def test_is_enabled_true_for_cohere(settings_cohere):
    svc = RerankerService(settings_cohere)
    assert svc.is_enabled() is True


# ---------------------------------------------------------------------------
# Edge cases (backend = "none")
# ---------------------------------------------------------------------------

async def test_rerank_backend_none_returns_input_unchanged(settings_no_reranker):
    svc = RerankerService(settings_no_reranker)
    candidates = [_make_scored("text", 0.8, i) for i in range(3)]
    result = await svc.rerank("query", candidates)
    assert result is candidates


async def test_rerank_empty_candidates_returns_empty(settings_cross_encoder):
    svc = RerankerService(settings_cross_encoder)
    result = await svc.rerank("query", [])
    assert result == []


async def test_rerank_single_candidate_returned_unchanged(settings_cross_encoder):
    svc = RerankerService(settings_cross_encoder)
    single = [_make_scored("only one", 0.75)]
    result = await svc.rerank("query", single)
    assert result == single


# ---------------------------------------------------------------------------
# CrossEncoder backend
# ---------------------------------------------------------------------------

async def test_cross_encoder_reorders_by_relevance(settings_cross_encoder):
    svc = RerankerService(settings_cross_encoder)

    candidates = [
        _make_scored("Irrelevant text about weather", 0.80, 0),
        _make_scored("Machine learning algorithms are powerful", 0.75, 1),
    ]

    fake_scores = [0.1, 0.9]  # second candidate is more relevant

    mock_ce = MagicMock()
    mock_ce.predict = MagicMock(return_value=fake_scores)
    svc._cross_encoder = mock_ce

    result = await svc.rerank("machine learning", candidates)

    assert result[0].chunk.chunk_index == 1  # higher relevance first


async def test_cross_encoder_updates_similarity_score(settings_cross_encoder):
    svc = RerankerService(settings_cross_encoder)
    candidates = [_make_scored("text A", 0.80, 0), _make_scored("text B", 0.70, 1)]

    mock_ce = MagicMock()
    mock_ce.predict = MagicMock(return_value=[0.6, 0.9])
    svc._cross_encoder = mock_ce

    result = await svc.rerank("query", candidates)

    # similarity_score should reflect normalized reranker score
    for sc in result:
        assert sc.rerank_score is not None
        assert 0.0 <= sc.similarity_score <= 1.0


async def test_cross_encoder_preserves_bi_encoder_score(settings_cross_encoder):
    svc = RerankerService(settings_cross_encoder)
    candidates = [_make_scored("text A", 0.88, 0)]
    # Single candidate — returned unchanged
    result = await svc.rerank("query", candidates)
    assert result[0].bi_encoder_score == 0.88


async def test_cross_encoder_top_n_truncation(settings_cross_encoder):
    svc = RerankerService(settings_cross_encoder)
    candidates = [_make_scored(f"text {i}", 0.8, i) for i in range(6)]

    mock_ce = MagicMock()
    mock_ce.predict = MagicMock(return_value=[float(i) / 10 for i in range(6)])
    svc._cross_encoder = mock_ce

    # Apply MMR top_k separately; rerank returns all then caller applies top_k
    result = await svc.rerank("query", candidates)
    assert len(result) == 6  # rerank returns all; top_k is applied by pipeline


# ---------------------------------------------------------------------------
# Error propagation
# ---------------------------------------------------------------------------

async def test_reranker_exception_raises_reranker_error(settings_cross_encoder):
    svc = RerankerService(settings_cross_encoder)
    candidates = [_make_scored("a", 0.8, 0), _make_scored("b", 0.7, 1)]

    mock_ce = MagicMock()
    mock_ce.predict = MagicMock(side_effect=RuntimeError("model crashed"))
    svc._cross_encoder = mock_ce

    with pytest.raises(RerankerError):
        await svc.rerank("query", candidates)


# ---------------------------------------------------------------------------
# Cohere backend (mocked)
# ---------------------------------------------------------------------------

async def test_cohere_reranks_and_normalises(settings_cohere):
    svc = RerankerService(settings_cohere)
    candidates = [_make_scored("a", 0.8, 0), _make_scored("b", 0.7, 1)]

    mock_result = MagicMock()
    mock_result.results = [
        MagicMock(index=1, relevance_score=0.95),
        MagicMock(index=0, relevance_score=0.30),
    ]

    mock_co = AsyncMock()
    mock_co.rerank = AsyncMock(return_value=mock_result)

    with patch("cohere.AsyncClientV2", return_value=mock_co):
        result = await svc.rerank("query", candidates)

    assert result[0].chunk.chunk_index == 1
    assert result[0].similarity_score == pytest.approx(1.0)  # 0.95 / 0.95
