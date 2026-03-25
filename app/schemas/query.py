"""
Query API Schemas
==================

Purpose:
    Pydantic models for the question-answering endpoints.
    Used by POST /api/v1/query and POST /api/v1/query/stream.

Schemas:

    QueryRequest:
        The user's question along with session context.
        Fields:
            question: str - the user's natural language question (required, min 1 char)
            session_id: str - UUID of the active session (required)
            document_ids: list[str] | None - optional filter to specific documents;
                if None, queries all documents in the session
            top_k: int | None - override default top-k retrieval count (3-10)
            stream: bool = False - whether to use SSE streaming

    CitationSchema:
        A single source reference in the response.
        Fields:
            document_name: str - original PDF filename
            page_numbers: list[int] - pages where cited info appears
            chunk_index: int - chunk position in the document
            chunk_id: str - unique chunk identifier
            excerpt: str - short supporting excerpt from the source chunk

    QueryResponse:
        The full answer returned for a non-streaming query.
        Fields:
            answer: str - the generated answer grounded in document content
            citations: list[CitationSchema] - source references
            session_id: str - the session this answer belongs to
            query_id: str - unique ID for this query (for logging/debugging)
            confidence: float - heuristic confidence score (0.0-1.0)
            retrieval_metadata: dict - diagnostics:
                - retrieval_time_ms: float
                - chunks_considered: int
                - chunks_used: int
                - similarity_scores: list[float]

    StreamingChunk:
        A single SSE event in the streaming response.
        Fields:
            event: str - "token" | "citation" | "done" | "error"
            data: str - token text, JSON citation, completion signal, or error message
            query_id: str

Validation Rules:
    - question must be non-empty and <= 2000 characters
    - session_id must be a valid UUID
    - top_k must be between 3 and 10 if provided
    - document_ids, if provided, must all be valid UUIDs

Dependencies:
    - pydantic (BaseModel, Field, validator)
    - uuid
"""
