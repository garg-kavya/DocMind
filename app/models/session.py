"""
Session Domain Model
=====================

Purpose:
    Represents a conversational Q&A session. A session binds together:
    - A set of uploaded documents (the knowledge base for this conversation)
    - A conversation history (for multi-turn follow-up questions)
    - Session-level configuration overrides (optional)

Attributes:
    session_id: str (UUID4)
        Unique session identifier, returned to the client on creation.

    document_ids: list[str]
        List of document_id values that are part of this session's
        knowledge base. Retrieval is scoped to these documents.

    conversation_history: list[ConversationTurn]
        Ordered list of (user_query, assistant_response, retrieved_chunk_ids,
        timestamp) tuples. Capped at MAX_CONVERSATION_TURNS (default: 10).

    created_at: datetime
        When the session was created.

    last_active_at: datetime
        Updated on every interaction. Used for TTL-based cleanup.

    config_overrides: dict | None
        Optional per-session overrides (e.g., different top_k, chunk_size
        for experimentation).

    ConversationTurn (nested dataclass):
        user_query: str
            The original question asked by the user.
        standalone_query: str
            The reformulated standalone version (after conversational
            context is resolved).
        assistant_response: str
            The generated answer.
        retrieved_chunk_ids: list[str]
            Chunk IDs used to generate this answer (for auditability).
        timestamp: datetime

Lifecycle:
    - Created via POST /api/v1/sessions
    - Populated as documents are uploaded and queries are made
    - Expired and cleaned up after SESSION_TTL_MINUTES of inactivity
    - Explicitly deletable via DELETE /api/v1/sessions/{session_id}

Dependencies:
    - uuid
    - datetime
    - dataclasses
"""
