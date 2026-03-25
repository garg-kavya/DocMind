"""
Query Endpoints
================

Purpose:
    Handles user questions against uploaded PDF documents. Supports both
    synchronous (full response) and streaming (SSE) modes.

Endpoints:

    POST /api/v1/query
        Ask a question and receive a complete answer with citations.

        Request Body (JSON):
            {
                "question": str,        # required, 1-2000 chars
                "session_id": str,      # required, valid UUID
                "document_ids": [str],  # optional, filter to specific docs
                "top_k": int,           # optional, 3-10, override retrieval count
                "stream": false         # must be false for this endpoint
            }

        Processing Flow:
            1. Validate session exists
            2. Reformulate query (if follow-up)
            3. Embed reformulated query
            4. Retrieve top-k relevant chunks (with MMR re-ranking)
            5. Generate answer with citation-aware prompt
            6. Extract and validate citations
            7. Update session history
            8. Return complete response

        Response: 200 OK
            {
                "answer": str,
                "citations": [
                    {
                        "document_name": str,
                        "page_numbers": [int],
                        "chunk_index": int,
                        "chunk_id": str,
                        "excerpt": str
                    }
                ],
                "session_id": str,
                "query_id": str,
                "confidence": float,
                "retrieval_metadata": {
                    "retrieval_time_ms": float,
                    "chunks_considered": int,
                    "chunks_used": int,
                    "similarity_scores": [float]
                }
            }

        Errors:
            400 — Invalid request (empty question, bad UUID, etc.)
            404 — Session not found
            404 — No documents in session
            500 — Generation failure

    POST /api/v1/query/stream
        Ask a question and receive a streaming SSE response.

        Request Body: Same as POST /api/v1/query (stream field ignored)

        Response: 200 OK
            Content-Type: text/event-stream
            Cache-Control: no-cache
            Connection: keep-alive

            SSE Events (in order):
                event: token
                data: {"text": "...", "query_id": "..."}
                ... (repeated for each token)

                event: citation
                data: {"citations": [...], "query_id": "..."}

                event: done
                data: {"query_id": "...", "total_tokens": int}

        Errors: Same as non-streaming, but sent as SSE error events

Dependencies:
    - fastapi (APIRouter, Depends, HTTPException)
    - fastapi.responses (StreamingResponse)
    - app.schemas.query (QueryRequest, QueryResponse, StreamingChunk)
    - app.dependencies (get_rag_chain, get_session_store)
    - app.chains.rag_chain (RAGChain)
    - app.services.streaming (StreamingHandler)
"""
