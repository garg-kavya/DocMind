"""
In-Memory Session Store
========================

Purpose:
    Manages conversational session state in memory. Each session tracks
    which documents are loaded and maintains the conversation history
    for multi-turn Q&A.

Storage Model:
    dict[str, Session] — session_id -> Session domain object

    This is intentionally in-memory (not a database) because:
    - Sessions are ephemeral (TTL-based expiry)
    - Sub-millisecond access is needed in the request path
    - Conversation history is small (10 turns max)
    - Horizontal scaling would use Redis (future extension point)

Session Lifecycle:
    1. Create: POST /api/v1/sessions -> generates UUID, stores Session
    2. Use: Each query updates last_active_at and appends to history
    3. Expire: Background task checks every SESSION_CLEANUP_INTERVAL_SECONDS
       and removes sessions where (now - last_active_at) > SESSION_TTL_MINUTES
    4. Delete: Explicit DELETE request removes session immediately

Methods:

    create_session(document_ids: list[str]) -> Session:
        Creates and stores a new session.
        Inputs: list of document IDs to associate
        Outputs: Session object with generated session_id

    get_session(session_id: str) -> Session | None:
        Retrieves a session by ID.
        Returns None if session doesn't exist or has expired.

    update_session(session_id: str, turn: ConversationTurn) -> Session:
        Appends a conversation turn to the session history.
        Updates last_active_at.
        Enforces MAX_CONVERSATION_TURNS (drops oldest turn if exceeded).

    add_document_to_session(session_id: str, document_id: str) -> Session:
        Associates an additional document with the session.

    delete_session(session_id: str) -> bool:
        Removes a session. Returns True if found and deleted.

    cleanup_expired() -> int:
        Removes all expired sessions. Returns count removed.
        Called periodically by background task.

Thread Safety:
    Uses asyncio.Lock for concurrent access safety in async context.

Dependencies:
    - asyncio
    - app.models.session (Session, ConversationTurn)
    - app.config (SessionSettings)
"""
