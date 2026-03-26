"""Integration tests for /api/v1/sessions endpoints."""
from __future__ import annotations

import uuid

import pytest


# ---------------------------------------------------------------------------
# POST /sessions
# ---------------------------------------------------------------------------

async def test_create_session_returns_201(test_client):
    response = await test_client.post("/api/v1/sessions", json={})
    assert response.status_code == 201


async def test_create_session_returns_session_id(test_client):
    response = await test_client.post("/api/v1/sessions", json={})
    body = response.json()
    assert "session_id" in body
    assert len(body["session_id"]) > 0


async def test_create_session_returns_expires_at(test_client):
    response = await test_client.post("/api/v1/sessions", json={})
    assert "expires_at" in response.json()


async def test_create_session_with_document_ids(test_client):
    response = await test_client.post(
        "/api/v1/sessions",
        json={"document_ids": ["doc-1", "doc-2"]},
    )
    assert response.status_code == 201
    body = response.json()
    assert "doc-1" in body["document_ids"]
    assert "doc-2" in body["document_ids"]


async def test_create_session_without_documents_has_empty_list(test_client):
    response = await test_client.post("/api/v1/sessions", json={})
    assert response.json()["document_ids"] == []


# ---------------------------------------------------------------------------
# GET /sessions/{session_id}
# ---------------------------------------------------------------------------

async def test_get_existing_session(test_client):
    create = await test_client.post("/api/v1/sessions", json={})
    session_id = create.json()["session_id"]

    response = await test_client.get(f"/api/v1/sessions/{session_id}")
    assert response.status_code == 200
    assert response.json()["session_id"] == session_id


async def test_get_nonexistent_session_returns_404(test_client):
    response = await test_client.get(f"/api/v1/sessions/{uuid.uuid4()}")
    assert response.status_code == 404


async def test_get_session_has_required_fields(test_client):
    create = await test_client.post("/api/v1/sessions", json={})
    session_id = create.json()["session_id"]

    response = await test_client.get(f"/api/v1/sessions/{session_id}")
    body = response.json()

    for field in ("session_id", "document_ids", "conversation_history",
                  "turn_count", "created_at", "last_active_at", "expires_at"):
        assert field in body


async def test_get_session_turn_count_zero_initially(test_client):
    create = await test_client.post("/api/v1/sessions", json={})
    session_id = create.json()["session_id"]

    response = await test_client.get(f"/api/v1/sessions/{session_id}")
    assert response.json()["turn_count"] == 0


async def test_get_session_history_empty_initially(test_client):
    create = await test_client.post("/api/v1/sessions", json={})
    session_id = create.json()["session_id"]

    response = await test_client.get(f"/api/v1/sessions/{session_id}")
    assert response.json()["conversation_history"] == []


# ---------------------------------------------------------------------------
# DELETE /sessions/{session_id}
# ---------------------------------------------------------------------------

async def test_delete_session_returns_200(test_client):
    create = await test_client.post("/api/v1/sessions", json={})
    session_id = create.json()["session_id"]

    response = await test_client.delete(f"/api/v1/sessions/{session_id}")
    assert response.status_code == 200


async def test_delete_session_returns_session_id(test_client):
    create = await test_client.post("/api/v1/sessions", json={})
    session_id = create.json()["session_id"]

    response = await test_client.delete(f"/api/v1/sessions/{session_id}")
    assert response.json()["session_id"] == session_id


async def test_delete_session_makes_it_inaccessible(test_client):
    create = await test_client.post("/api/v1/sessions", json={})
    session_id = create.json()["session_id"]
    await test_client.delete(f"/api/v1/sessions/{session_id}")

    response = await test_client.get(f"/api/v1/sessions/{session_id}")
    assert response.status_code == 404


async def test_delete_nonexistent_session_returns_404(test_client):
    response = await test_client.delete(f"/api/v1/sessions/{uuid.uuid4()}")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Multiple sessions
# ---------------------------------------------------------------------------

async def test_multiple_sessions_are_independent(test_client):
    r1 = await test_client.post("/api/v1/sessions", json={})
    r2 = await test_client.post("/api/v1/sessions", json={})

    sid1 = r1.json()["session_id"]
    sid2 = r2.json()["session_id"]
    assert sid1 != sid2

    g1 = await test_client.get(f"/api/v1/sessions/{sid1}")
    g2 = await test_client.get(f"/api/v1/sessions/{sid2}")
    assert g1.status_code == 200
    assert g2.status_code == 200
