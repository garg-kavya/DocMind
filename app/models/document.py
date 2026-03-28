"""Document domain model."""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.schemas.metadata import IngestionMetadata, PDFMetadata

DocumentStatus = str  # "uploaded" | "processing" | "ready" | "error"


@dataclass
class Document:
    filename: str
    file_path: str
    file_size_bytes: int
    document_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    status: DocumentStatus = "uploaded"
    page_count: int = 0
    total_chunks: int = 0
    pdf_metadata: "PDFMetadata | None" = None
    ingestion_metadata: "IngestionMetadata | None" = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    processed_at: datetime | None = None
    error_message: str | None = None
