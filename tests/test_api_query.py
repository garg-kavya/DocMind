"""
Query API Integration Tests
=============================

Purpose:
    End-to-end tests for the question-answering endpoints.

Test Cases:

    test_query_returns_answer_with_citations:
        Create session, upload document, query, and assert response
        contains answer text and at least one citation.

    test_query_invalid_session:
        Query with non-existent session_id and assert 404.

    test_query_empty_question:
        Query with empty string and assert 400.

    test_query_streaming_response:
        Query the /stream endpoint and assert SSE events are received
        in correct order (token*, citation, done).

    test_follow_up_query:
        Ask two sequential questions and assert the second query's
        response shows awareness of the first turn's context.

    test_query_with_top_k_override:
        Query with custom top_k and assert the retrieval_metadata
        reflects the override.

    test_query_no_relevant_context:
        Query about a topic not in the documents and assert the
        response indicates no relevant information found.

Dependencies:
    - pytest
    - pytest-asyncio
    - httpx (AsyncClient)
    - app.main
"""
