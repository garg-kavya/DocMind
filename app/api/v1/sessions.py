"""
Session Management Endpoints
==============================

Purpose:
    Manages conversational Q&A sessions. A session ties together uploaded
    documents and conversation history for multi-turn interactions.

Endpoints:

    POST /api/v1/sessions
        Create a new conversational session.

        Request Body (JSON):
            {
                "document_ids": [str] | null,   # optional: pre-load documents
                "config_overrides": dict | null  # optional: per-session config
            }

        Response: 201 Created
            {
                "session_id": str,
                "document_ids": [str],
                "created_at": datetime,
                "expires_at": datetime,
                "message": "Session created successfully"
            }

    GET /api/v1/sessions/{session_id}
        Retrieve session details including full conversation history.

        Response: 200 OK
            {
                "session_id": str,
                "document_ids": [str],
                "conversation_history": [
                    {
                        "turn_index": int,
                        "user_query": str,
                        "standalone_query": str,
                        "assistant_response": str,
                        "citations": [...],
                        "timestamp": datetime
                    }
                ],
                "turn_count": int,
                "created_at": datetime,
                "last_active_at": datetime,
                "expires_at": datetime
            }

        Errors:
            404 — Session not found or expired

    DELETE /api/v1/sessions/{session_id}
        End a session and clear its conversation history.

        Response: 200 OK
            {
                "session_id": str,
                "message": "Session deleted successfully",
                "turns_cleared": int
            }

        Errors:
            404 — Session not found

Dependencies:
    - fastapi (APIRouter, Depends, HTTPException)
    - app.schemas.session (all session schemas)
    - app.dependencies (get_session_store)
    - app.db.session_store (SessionStore)
"""
