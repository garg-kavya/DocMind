"""Document API request/response schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    file_size_bytes: int
    status: str
    message: str
    created_at: datetime


class DocumentStatusResponse(BaseModel):
    document_id: str
    filename: str
    status: str
    page_count: int
    total_chunks: int
    pdf_metadata: dict | None = None
    ingestion_metadata: dict | None = None
    created_at: datetime
    processed_at: datetime | None = None
    error_message: str | None = None


class DocumentListResponse(BaseModel):
    documents: list[DocumentStatusResponse]
    total_count: int


class DocumentDeleteResponse(BaseModel):
    document_id: str
    message: str
    chunks_removed: int
