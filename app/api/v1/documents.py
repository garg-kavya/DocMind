"""
Document Management Endpoints
===============================

Purpose:
    Handles PDF document upload, status checking, listing, and deletion.
    These endpoints manage the ingestion side of the RAG pipeline.

Endpoints:

    POST /api/v1/documents/upload
        Upload a PDF document for processing.

        Request:
            Content-Type: multipart/form-data
            Body:
                file: UploadFile (required) — the PDF file
                session_id: str (optional) — auto-associate with a session

        Processing Pipeline (triggered async after upload):
            1. Validate file (PDF, size limit, non-empty)
            2. Save to uploads/ directory
            3. Parse PDF (PyMuPDF with pdfplumber fallback)
            4. Clean extracted text
            5. Chunk text into 512-token segments
            6. Embed all chunks via OpenAI API
            7. Store vectors in vector database
            8. Update document status to "ready"

        Response: 202 Accepted
            DocumentUploadResponse (document_id, status="processing", ...)

        Errors:
            400 — Invalid file type (not PDF)
            400 — File too large (> MAX_UPLOAD_SIZE_MB)
            400 — Empty file
            500 — Processing pipeline failure

    GET /api/v1/documents/{document_id}
        Retrieve document status and metadata.

        Response: 200 OK
            DocumentStatusResponse

        Errors:
            404 — Document not found

    GET /api/v1/documents
        List all uploaded documents.

        Query Parameters:
            status: str (optional) — filter by status
            limit: int = 50 — pagination
            offset: int = 0

        Response: 200 OK
            DocumentListResponse

    DELETE /api/v1/documents/{document_id}
        Remove a document and all its vectors from the store.

        Response: 200 OK
            DocumentDeleteResponse

        Errors:
            404 — Document not found

Dependencies:
    - fastapi (APIRouter, UploadFile, File, Depends, HTTPException)
    - app.schemas.document (all response schemas)
    - app.dependencies (get_pdf_processor, get_vector_store, get_session_store)
    - app.services.pdf_processor
    - app.services.text_cleaner
    - app.services.chunker
    - app.services.embedder
"""
