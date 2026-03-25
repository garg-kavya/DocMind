"""
Document API Integration Tests
================================

Purpose:
    End-to-end tests for the document management endpoints.
    Uses FastAPI TestClient with mocked external services.

Test Cases:

    test_upload_valid_pdf:
        POST a valid PDF and assert 202 response with document_id.

    test_upload_non_pdf_rejected:
        POST a non-PDF file and assert 400 error.

    test_upload_oversized_rejected:
        POST a file exceeding MAX_UPLOAD_SIZE_MB and assert 400 error.

    test_get_document_status:
        Upload a PDF, then GET its status and assert correct fields.

    test_get_nonexistent_document:
        GET a random UUID and assert 404.

    test_list_documents:
        Upload multiple PDFs, then GET /documents and assert all returned.

    test_delete_document:
        Upload, then DELETE, then GET and assert 404.

    test_upload_with_session_id:
        Upload with session_id parameter and assert document is
        associated with the session.

Dependencies:
    - pytest
    - pytest-asyncio
    - httpx (AsyncClient)
    - app.main (FastAPI app)
"""
