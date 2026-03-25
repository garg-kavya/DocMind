"""
Document Domain Model
======================

Purpose:
    Represents a PDF document that has been uploaded and processed by the system.
    This is the top-level entity in the document hierarchy:
    Document -> Pages -> Chunks

Attributes:
    document_id: str (UUID4)
        Unique identifier assigned at upload time.

    filename: str
        Original filename as provided by the user (e.g., "annual_report_2024.pdf").

    file_path: str
        Server-side path where the uploaded PDF is stored.

    file_size_bytes: int
        Size of the uploaded file for validation and metadata.

    page_count: int
        Total number of pages extracted from the PDF.

    total_chunks: int
        Number of chunks produced after the chunking pipeline.

    status: str
        Processing status. One of:
        "uploaded" -> "processing" -> "ready" -> "error"

    metadata: dict
        PDF metadata extracted during parsing:
        - title: str | None
        - author: str | None
        - creation_date: str | None
        - producer: str | None

    created_at: datetime
        Timestamp of upload.

    processed_at: datetime | None
        Timestamp when processing completed (or None if still processing).

    error_message: str | None
        Error details if status == "error".

Relationships:
    - Has many Chunk objects (stored in vector DB with document_id reference)
    - Referenced by Session objects (which documents are loaded in a session)

Dependencies:
    - uuid (for ID generation)
    - datetime
"""
