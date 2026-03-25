"""
Document API Schemas
=====================

Purpose:
    Pydantic models for document-related API request validation and response
    serialization. Used by the POST /api/v1/documents/upload and
    GET /api/v1/documents/{document_id} endpoints.

Schemas:

    DocumentUploadResponse:
        Returned after a successful PDF upload.
        Fields:
            document_id: str - UUID of the uploaded document
            filename: str - original filename
            file_size_bytes: int - file size
            page_count: int - number of PDF pages
            total_chunks: int - number of chunks created
            status: str - "processing" | "ready" | "error"
            message: str - human-readable status message
            created_at: datetime

    DocumentStatusResponse:
        Returned by GET /api/v1/documents/{document_id}.
        Fields:
            document_id: str
            filename: str
            status: str
            page_count: int
            total_chunks: int
            metadata: dict - PDF metadata (title, author, etc.)
            created_at: datetime
            processed_at: datetime | None
            error_message: str | None

    DocumentListResponse:
        Returned by GET /api/v1/documents (list all documents).
        Fields:
            documents: list[DocumentStatusResponse]
            total_count: int

    DocumentDeleteResponse:
        Returned by DELETE /api/v1/documents/{document_id}.
        Fields:
            document_id: str
            message: str
            chunks_removed: int

Validation Rules:
    - Upload accepts only application/pdf MIME type
    - Max file size: configurable (default 50MB)
    - Filename must be non-empty

Dependencies:
    - pydantic (BaseModel, Field, validator)
    - datetime
"""
