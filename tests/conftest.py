"""
Test Fixtures and Configuration
=================================

Purpose:
    Shared pytest fixtures used across all test modules. Provides mock
    services, test data, and a configured FastAPI test client.

Fixtures:

    test_client() -> AsyncClient:
        FastAPI TestClient with dependency overrides.
        Replaces real services with mocks to avoid external API calls.

    sample_pdf_bytes() -> bytes:
        A minimal valid PDF file in memory for upload testing.

    sample_document() -> Document:
        A pre-populated Document domain object.

    sample_chunks() -> list[Chunk]:
        A list of pre-populated Chunk objects with embeddings.

    mock_embedder() -> MockEmbeddingService:
        Returns deterministic embeddings (no OpenAI API calls).

    mock_vector_store() -> MockVectorStore:
        In-memory dict-based vector store for testing retrieval logic.

    mock_generator() -> MockGeneratorService:
        Returns canned answers with predictable citations.

    session_store() -> SessionStore:
        A real SessionStore instance (in-memory, no external deps).

    sample_session() -> Session:
        A pre-populated session with documents and conversation history.

Configuration:
    - Tests use a separate .env.test file (or env var overrides)
    - OPENAI_API_KEY is not required for unit tests (mocked)
    - Integration tests (marked @pytest.mark.integration) do call real APIs

Dependencies:
    - pytest
    - pytest-asyncio
    - httpx (AsyncClient for FastAPI testing)
    - unittest.mock
    - app.main (FastAPI app)
    - app.dependencies (for dependency overrides)
"""
