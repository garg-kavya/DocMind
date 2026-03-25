"""
Session API Integration Tests
================================

Purpose:
    End-to-end tests for session management endpoints.

Test Cases:

    test_create_session:
        POST /sessions and assert 201 with session_id and expires_at.

    test_create_session_with_documents:
        Create session with document_ids and assert they're associated.

    test_get_session_details:
        Create session, make queries, then GET and assert conversation
        history is present.

    test_get_nonexistent_session:
        GET with random UUID and assert 404.

    test_delete_session:
        Create, then DELETE, then GET and assert 404.

    test_session_expiry:
        Create session, wait (or mock time), and assert session
        is no longer accessible after TTL.

    test_conversation_history_ordering:
        Make multiple queries and assert turns are in chronological order.

    test_max_conversation_turns:
        Make MAX_CONVERSATION_TURNS + 1 queries and assert oldest turn
        is dropped.

Dependencies:
    - pytest
    - pytest-asyncio
    - httpx (AsyncClient)
    - app.main
"""
