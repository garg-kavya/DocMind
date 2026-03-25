"""
Session API Schemas
====================

Purpose:
    Pydantic models for session management endpoints.
    Used by POST /api/v1/sessions, GET /api/v1/sessions/{session_id},
    and DELETE /api/v1/sessions/{session_id}.

Schemas:

    SessionCreateRequest:
        Fields:
            document_ids: list[str] | None - optional list of document IDs
                to pre-load into the session. Documents can also be added
                later via upload with session_id.
            config_overrides: dict | None - optional per-session config
                (e.g., {"top_k": 7, "chunk_size_tokens": 256})

    SessionCreateResponse:
        Fields:
            session_id: str - UUID of the new session
            document_ids: list[str] - documents loaded in this session
            created_at: datetime
            expires_at: datetime - when session will auto-expire
            message: str

    ConversationTurnSchema:
        Fields:
            turn_index: int - 0-based position in conversation
            user_query: str - original question
            standalone_query: str - reformulated standalone version
            assistant_response: str - generated answer
            citations: list[CitationSchema] - sources for this turn
            timestamp: datetime

    SessionDetailResponse:
        Fields:
            session_id: str
            document_ids: list[str]
            conversation_history: list[ConversationTurnSchema]
            turn_count: int
            created_at: datetime
            last_active_at: datetime
            expires_at: datetime

    SessionDeleteResponse:
        Fields:
            session_id: str
            message: str
            turns_cleared: int

Dependencies:
    - pydantic (BaseModel, Field)
    - datetime
    - app.schemas.query (CitationSchema)
"""
