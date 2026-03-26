"""Integration tests for /api/v1/documents endpoints."""
from __future__ import annotations

import io
import uuid

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pdf_upload(content: bytes, filename: str = "test.pdf"):
    return {"file": (filename, io.BytesIO(content), "application/pdf")}


# ---------------------------------------------------------------------------
# POST /documents/upload
# ---------------------------------------------------------------------------

async def test_upload_valid_pdf_returns_202(test_client, sample_pdf_bytes):
    response = await test_client.post(
        "/api/v1/documents/upload",
        files=_pdf_upload(sample_pdf_bytes),
    )
    assert response.status_code == 202


async def test_upload_valid_pdf_returns_document_id(test_client, sample_pdf_bytes):
    response = await test_client.post(
        "/api/v1/documents/upload",
        files=_pdf_upload(sample_pdf_bytes),
    )
    body = response.json()
    assert "document_id" in body
    assert len(body["document_id"]) > 0


async def test_upload_returns_processing_status(test_client, sample_pdf_bytes):
    response = await test_client.post(
        "/api/v1/documents/upload",
        files=_pdf_upload(sample_pdf_bytes),
    )
    assert response.json()["status"] == "processing"


async def test_upload_non_pdf_rejected(test_client):
    fake_bytes = b"\xff\xd8\xff\xe0JFIF"  # JPEG magic
    response = await test_client.post(
        "/api/v1/documents/upload",
        files=_pdf_upload(fake_bytes, "image.jpg"),
    )
    assert response.status_code in (400, 422)


async def test_upload_empty_file_rejected(test_client):
    response = await test_client.post(
        "/api/v1/documents/upload",
        files=_pdf_upload(b""),
    )
    assert response.status_code in (400, 422)


async def test_upload_with_session_id(test_client, sample_pdf_bytes, sample_session):
    response = await test_client.post(
        "/api/v1/documents/upload",
        files=_pdf_upload(sample_pdf_bytes),
        data={"session_id": sample_session.session_id},
    )
    assert response.status_code == 202


# ---------------------------------------------------------------------------
# GET /documents/{document_id}
# ---------------------------------------------------------------------------

async def test_get_existing_document(test_client, sample_pdf_bytes):
    upload = await test_client.post(
        "/api/v1/documents/upload",
        files=_pdf_upload(sample_pdf_bytes),
    )
    doc_id = upload.json()["document_id"]

    response = await test_client.get(f"/api/v1/documents/{doc_id}")
    assert response.status_code == 200
    body = response.json()
    assert body["document_id"] == doc_id


async def test_get_nonexistent_document_returns_404(test_client):
    response = await test_client.get(f"/api/v1/documents/{uuid.uuid4()}")
    assert response.status_code == 404


async def test_get_document_has_required_fields(test_client, sample_pdf_bytes):
    upload = await test_client.post(
        "/api/v1/documents/upload",
        files=_pdf_upload(sample_pdf_bytes),
    )
    doc_id = upload.json()["document_id"]

    response = await test_client.get(f"/api/v1/documents/{doc_id}")
    body = response.json()

    for field in ("document_id", "filename", "status", "page_count", "total_chunks"):
        assert field in body


# ---------------------------------------------------------------------------
# GET /documents
# ---------------------------------------------------------------------------

async def test_list_documents_empty(test_client):
    response = await test_client.get("/api/v1/documents")
    assert response.status_code == 200
    body = response.json()
    assert "documents" in body
    assert "total_count" in body


async def test_list_documents_includes_uploaded(test_client, sample_pdf_bytes):
    await test_client.post(
        "/api/v1/documents/upload",
        files=_pdf_upload(sample_pdf_bytes),
    )
    response = await test_client.get("/api/v1/documents")
    assert response.json()["total_count"] >= 1


# ---------------------------------------------------------------------------
# DELETE /documents/{document_id}
# ---------------------------------------------------------------------------

async def test_delete_existing_document(test_client, sample_pdf_bytes):
    upload = await test_client.post(
        "/api/v1/documents/upload",
        files=_pdf_upload(sample_pdf_bytes),
    )
    doc_id = upload.json()["document_id"]

    delete_resp = await test_client.delete(f"/api/v1/documents/{doc_id}")
    assert delete_resp.status_code == 200
    assert delete_resp.json()["document_id"] == doc_id


async def test_delete_nonexistent_document_returns_404(test_client):
    response = await test_client.delete(f"/api/v1/documents/{uuid.uuid4()}")
    assert response.status_code == 404


async def test_delete_removes_document_from_list(test_client, sample_pdf_bytes):
    upload = await test_client.post(
        "/api/v1/documents/upload",
        files=_pdf_upload(sample_pdf_bytes),
    )
    doc_id = upload.json()["document_id"]
    await test_client.delete(f"/api/v1/documents/{doc_id}")

    response = await test_client.get(f"/api/v1/documents/{doc_id}")
    assert response.status_code == 404
