"""Integration tests for /api/v1/query endpoints."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock

import pytest

from app.models.query import (
    Citation,
    GeneratedAnswer,
    PipelineMetadata,
    StreamingChunk,
)
from app.schemas.metadata import RetrievalMetadata


def _make_answer(session_id: str = "s1") -> GeneratedAnswer:
    qid = str(uuid.uuid4())
    meta = PipelineMetadata(
        query_id=qid,
        total_time_ms=120.0,
        embedding_time_ms=15.0,
        retrieval_time_ms=10.0,
        generation_time_ms=90.0,
        memory_read_time_ms=2.0,
        memory_write_time_ms=3.0,
    )
    return GeneratedAnswer(
        answer_text="Machine learning is a subset of AI. [Source 1]",
        citations=[Citation(
            document_name="test.pdf",
            page_numbers=[1],
            chunk_index=0,
            chunk_id=str(uuid.uuid4()),
            excerpt="Machine learning content.",
        )],
        confidence=0.87,
        query_id=qid,
        cache_hit=False,
        retrieval_context=None,
        pipeline_metadata=meta,
    )


# ---------------------------------------------------------------------------
# POST /query
# ---------------------------------------------------------------------------

async def test_query_returns_200(test_client):
    session = await test_client.post("/api/v1/sessions", json={})
    session_id = session.json()["session_id"]

    test_client._test.rag_pipeline.run = AsyncMock(return_value=_make_answer(session_id))

    response = await test_client.post("/api/v1/query", json={
        "question": "What is machine learning?",
        "session_id": session_id,
        "document_ids": ["doc-1"],
    })
    assert response.status_code == 200


async def test_query_returns_answer_and_citations(test_client):
    session = await test_client.post("/api/v1/sessions", json={})
    session_id = session.json()["session_id"]
    test_client._test.rag_pipeline.run = AsyncMock(return_value=_make_answer(session_id))

    response = await test_client.post("/api/v1/query", json={
        "question": "What is ML?",
        "session_id": session_id,
        "document_ids": ["doc-1"],
    })
    body = response.json()

    assert "answer" in body
    assert "citations" in body
    assert isinstance(body["citations"], list)


async def test_query_response_has_required_fields(test_client):
    session = await test_client.post("/api/v1/sessions", json={})
    session_id = session.json()["session_id"]
    test_client._test.rag_pipeline.run = AsyncMock(return_value=_make_answer(session_id))

    response = await test_client.post("/api/v1/query", json={
        "question": "What is AI?",
        "session_id": session_id,
    })
    body = response.json()

    for field in ("answer", "citations", "session_id", "query_id", "confidence", "cache_hit"):
        assert field in body


async def test_query_empty_question_rejected(test_client):
    session = await test_client.post("/api/v1/sessions", json={})
    session_id = session.json()["session_id"]

    response = await test_client.post("/api/v1/query", json={
        "question": "",
        "session_id": session_id,
    })
    assert response.status_code == 422


async def test_query_whitespace_question_rejected(test_client):
    session = await test_client.post("/api/v1/sessions", json={})
    session_id = session.json()["session_id"]

    response = await test_client.post("/api/v1/query", json={
        "question": "   ",
        "session_id": session_id,
    })
    assert response.status_code == 422


async def test_query_with_top_k_override(test_client):
    session = await test_client.post("/api/v1/sessions", json={})
    session_id = session.json()["session_id"]
    test_client._test.rag_pipeline.run = AsyncMock(return_value=_make_answer(session_id))

    response = await test_client.post("/api/v1/query", json={
        "question": "What is deep learning?",
        "session_id": session_id,
        "top_k": 3,
    })
    assert response.status_code == 200
    call_kwargs = test_client._test.rag_pipeline.run.call_args
    assert call_kwargs.kwargs.get("top_k") == 3


async def test_query_confidence_between_0_and_1(test_client):
    session = await test_client.post("/api/v1/sessions", json={})
    session_id = session.json()["session_id"]
    test_client._test.rag_pipeline.run = AsyncMock(return_value=_make_answer(session_id))

    response = await test_client.post("/api/v1/query", json={
        "question": "Question here?",
        "session_id": session_id,
    })
    confidence = response.json()["confidence"]
    assert 0.0 <= confidence <= 1.0


async def test_query_session_id_in_response(test_client):
    session = await test_client.post("/api/v1/sessions", json={})
    session_id = session.json()["session_id"]
    test_client._test.rag_pipeline.run = AsyncMock(return_value=_make_answer(session_id))

    response = await test_client.post("/api/v1/query", json={
        "question": "What is NLP?",
        "session_id": session_id,
    })
    assert response.json()["session_id"] == session_id


# ---------------------------------------------------------------------------
# POST /query/stream
# ---------------------------------------------------------------------------

async def test_query_stream_returns_event_stream(test_client):
    session = await test_client.post("/api/v1/sessions", json={})
    session_id = session.json()["session_id"]

    async def _fake_stream(*args, **kwargs):
        yield StreamingChunk(event="token", data={"text": "Hello", "query_id": "q1"})
        yield StreamingChunk(event="citation", data={"citations": [], "query_id": "q1"})
        yield StreamingChunk(event="done", data={"query_id": "q1"})

    test_client._test.rag_pipeline.run_stream = _fake_stream

    response = await test_client.post("/api/v1/query/stream", json={
        "question": "What is ML?",
        "session_id": session_id,
    })
    assert response.status_code == 200
    assert "text/event-stream" in response.headers.get("content-type", "")


async def test_query_stream_contains_events(test_client):
    session = await test_client.post("/api/v1/sessions", json={})
    session_id = session.json()["session_id"]

    async def _fake_stream(*args, **kwargs):
        yield StreamingChunk(event="token", data={"text": "Word", "query_id": "q1"})
        yield StreamingChunk(event="done", data={"query_id": "q1"})

    test_client._test.rag_pipeline.run_stream = _fake_stream

    response = await test_client.post("/api/v1/query/stream", json={
        "question": "Question?",
        "session_id": session_id,
    })
    content = response.text
    assert "event: token" in content or "token" in content


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

async def test_health_check_returns_200_or_503(test_client):
    response = await test_client.get("/api/v1/health")
    assert response.status_code in (200, 503)


async def test_health_check_has_status_field(test_client):
    response = await test_client.get("/api/v1/health")
    assert "status" in response.json()
