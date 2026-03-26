"""Tests for RAGChain — answer generation, citation extraction, streaming."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.chains.rag_chain import RAGChain
from app.models.chunk import Chunk
from app.models.query import (
    Citation,
    QueryContext,
    RetrievedContext,
    ScoredChunk,
    StreamingChunk,
)
from app.schemas.metadata import RetrievalMetadata


def _make_scored_chunk(text: str, rank: int, score: float = 0.85) -> ScoredChunk:
    chunk = Chunk(
        document_id="doc-1",
        document_name="report.pdf",
        chunk_index=rank - 1,
        text=text,
        token_count=len(text.split()),
        page_numbers=[rank],
        start_char_offset=(rank - 1) * 200,
        end_char_offset=rank * 200,
    )
    sc = ScoredChunk(chunk=chunk, similarity_score=score, bi_encoder_score=score)
    sc.rank = rank
    return sc


def _make_retrieved(scored_chunks: list[ScoredChunk]) -> RetrievedContext:
    meta = RetrievalMetadata(
        retrieval_time_ms=10.0,
        candidates_considered=len(scored_chunks),
        candidates_after_threshold=len(scored_chunks),
        chunks_used=len(scored_chunks),
        similarity_scores=[sc.similarity_score for sc in scored_chunks],
        top_k_requested=5,
        similarity_threshold_used=0.70,
    )
    return RetrievedContext(chunks=scored_chunks, retrieval_metadata=meta)


def _make_query_context(session_id: str | None = None) -> QueryContext:
    return QueryContext(
        raw_query="What is machine learning?",
        standalone_query="What is machine learning?",
        session_id=session_id or str(uuid.uuid4()),
        document_ids=["doc-1"],
        query_id=str(uuid.uuid4()),
        formatted_history="",
    )


@pytest.fixture
def chain(settings) -> RAGChain:
    return RAGChain(settings)


# ---------------------------------------------------------------------------
# invoke() — mocked OpenAI call
# ---------------------------------------------------------------------------

async def test_invoke_returns_generated_answer(chain):
    sc = _make_scored_chunk("Machine learning uses data. [Source 1]", 1, 0.90)
    retrieved = _make_retrieved([sc])
    query_ctx = _make_query_context()

    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="ML uses data. [Source 1]"))]

    with patch.object(chain._client.chat.completions, "create",
                      new_callable=AsyncMock, return_value=mock_response):
        answer = await chain.invoke(query_ctx, retrieved)

    assert "ML uses data." in answer.answer_text
    assert answer.query_id == query_ctx.query_id
    assert answer.cache_hit is False


async def test_invoke_extracts_citations(chain):
    sc = _make_scored_chunk("Deep learning is powerful.", 1, 0.88)
    retrieved = _make_retrieved([sc])
    query_ctx = _make_query_context()

    mock_response = MagicMock()
    mock_response.choices = [MagicMock(
        message=MagicMock(content="Deep learning is powerful. [Source 1]")
    )]

    with patch.object(chain._client.chat.completions, "create",
                      new_callable=AsyncMock, return_value=mock_response):
        answer = await chain.invoke(query_ctx, retrieved)

    assert len(answer.citations) == 1
    assert answer.citations[0].document_name == "report.pdf"


async def test_invoke_hallucinated_source_not_included(chain):
    sc = _make_scored_chunk("Real content.", 1, 0.90)
    retrieved = _make_retrieved([sc])
    query_ctx = _make_query_context()

    mock_response = MagicMock()
    # [Source 99] does not exist in context
    mock_response.choices = [MagicMock(
        message=MagicMock(content="Real answer [Source 1] and fake [Source 99].")
    )]

    with patch.object(chain._client.chat.completions, "create",
                      new_callable=AsyncMock, return_value=mock_response):
        answer = await chain.invoke(query_ctx, retrieved)

    citation_ranks = {c.chunk_index + 1 for c in answer.citations}
    assert 99 not in citation_ranks


async def test_invoke_no_context_returns_fallback_answer(chain):
    retrieved = _make_retrieved([])  # empty context
    query_ctx = _make_query_context()

    mock_response = MagicMock()
    mock_response.choices = [MagicMock(
        message=MagicMock(content="I could not find relevant information.")
    )]

    with patch.object(chain._client.chat.completions, "create",
                      new_callable=AsyncMock, return_value=mock_response):
        answer = await chain.invoke(query_ctx, retrieved)

    assert answer.citations == []
    assert answer.confidence == 0.0


async def test_invoke_confidence_between_0_and_1(chain):
    sc = _make_scored_chunk("Relevant content.", 1, 0.85)
    retrieved = _make_retrieved([sc])
    query_ctx = _make_query_context()

    mock_response = MagicMock()
    mock_response.choices = [MagicMock(
        message=MagicMock(content="Answer based on [Source 1].")
    )]

    with patch.object(chain._client.chat.completions, "create",
                      new_callable=AsyncMock, return_value=mock_response):
        answer = await chain.invoke(query_ctx, retrieved)

    assert 0.0 <= answer.confidence <= 1.0


async def test_invoke_conversation_history_included_in_prompt(chain):
    sc = _make_scored_chunk("Context here.", 1, 0.88)
    retrieved = _make_retrieved([sc])
    query_ctx = _make_query_context()
    query_ctx.formatted_history = "User: previous Q\nAssistant: previous A"

    captured_messages = []

    async def _fake_create(**kwargs):
        captured_messages.extend(kwargs.get("messages", []))
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock(message=MagicMock(content="Answer."))]
        return mock_resp

    with patch.object(chain._client.chat.completions, "create",
                      new_callable=AsyncMock, side_effect=_fake_create):
        await chain.invoke(query_ctx, retrieved)

    full_prompt = " ".join(m["content"] for m in captured_messages)
    assert "previous Q" in full_prompt


# ---------------------------------------------------------------------------
# stream() — mocked OpenAI streaming
# ---------------------------------------------------------------------------

async def test_stream_yields_token_events(chain):
    sc = _make_scored_chunk("Content for streaming.", 1, 0.88)
    retrieved = _make_retrieved([sc])
    query_ctx = _make_query_context()

    async def _fake_stream(*args, **kwargs):
        for word in ["Hello", " world"]:
            chunk = MagicMock()
            chunk.choices = [MagicMock(delta=MagicMock(content=word))]
            yield chunk

    mock_stream = MagicMock()
    mock_stream.__aiter__ = _fake_stream

    with patch.object(chain._client.chat.completions, "create",
                      new_callable=AsyncMock, return_value=mock_stream):
        events = []
        async for chunk in chain.stream(query_ctx, retrieved):
            events.append(chunk)

    token_events = [e for e in events if e.event == "token"]
    assert len(token_events) >= 1


async def test_stream_yields_citation_event_last(chain):
    sc = _make_scored_chunk("Content.", 1, 0.88)
    retrieved = _make_retrieved([sc])
    query_ctx = _make_query_context()

    async def _fake_stream(*args, **kwargs):
        chunk = MagicMock()
        chunk.choices = [MagicMock(delta=MagicMock(content="text [Source 1]"))]
        yield chunk

    mock_stream = MagicMock()
    mock_stream.__aiter__ = _fake_stream

    with patch.object(chain._client.chat.completions, "create",
                      new_callable=AsyncMock, return_value=mock_stream):
        events = []
        async for e in chain.stream(query_ctx, retrieved):
            events.append(e)

    assert events[-1].event == "citation"


# ---------------------------------------------------------------------------
# _compute_confidence
# ---------------------------------------------------------------------------

def test_confidence_zero_for_no_context(chain):
    retrieved = _make_retrieved([])
    conf = chain._compute_confidence("", retrieved, [])
    assert conf == 0.0


def test_confidence_higher_with_citations(chain):
    sc = _make_scored_chunk("Content.", 1, 0.90)
    retrieved = _make_retrieved([sc])
    fake_citation = Citation(
        document_name="r.pdf", page_numbers=[1], chunk_index=0,
        chunk_id="c1", excerpt="Content."
    )
    conf_with = chain._compute_confidence("Answer [Source 1].", retrieved, [fake_citation])
    conf_without = chain._compute_confidence("Answer.", retrieved, [])
    assert conf_with >= conf_without


def test_uncertainty_penalty_applied(chain):
    sc = _make_scored_chunk("Content.", 1, 0.90)
    retrieved = _make_retrieved([sc])
    conf_normal = chain._compute_confidence("Clear answer.", retrieved, [])
    conf_uncertain = chain._compute_confidence(
        "I cannot find the information.", retrieved, []
    )
    assert conf_uncertain < conf_normal
