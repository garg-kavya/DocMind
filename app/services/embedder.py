"""
Embedding Service
==================

Purpose:
    Generates vector embeddings for text chunks and queries using the
    OpenAI Embeddings API. Embeddings are the numeric representation that
    enables semantic similarity search in the vector database.

Pipeline Position:
    Ingestion: Upload -> Parse -> Clean -> Chunk -> **Embed** -> Store
    Query:     User Question -> Reformulate -> **Embed** -> Retrieve -> Generate

Embedding Model:
    text-embedding-3-small (OpenAI)
    - Dimensions: 1536
    - Normalized output: vectors have unit L2 norm
    - Cost-effective for production use
    - Strong performance on retrieval benchmarks
    - Alternative: text-embedding-3-large (3072 dims) for higher precision
      at 2x cost — configurable via settings

Batch Processing:
    Document ingestion embeds all chunks in batches:
    - Batch size: 100 chunks per API call (configurable)
    - Async batching: concurrent batch calls for large documents
    - Rate limit handling: exponential backoff on 429 responses

    Query embedding is a single API call (~100-150ms latency).

Methods:

    embed_chunks(chunks: list[Chunk]) -> list[Chunk]:
        Embeds all chunks in batches. Populates the chunk.embedding field.
        Inputs: list of Chunk objects with text populated
        Outputs: same chunks with embedding field filled
        Side effects: OpenAI API calls

    embed_query(query_text: str) -> list[float]:
        Embeds a single query string.
        Inputs: query text (standalone, reformulated query)
        Outputs: 1536-dimensional embedding vector
        Latency: ~100-150ms

Performance Considerations:
    - Batch embedding at ingestion time means zero embedding latency for
      stored documents at query time
    - Query embedding is the only per-request embedding call (~100ms)
    - Connection pooling via httpx.AsyncClient for OpenAI API
    - Embedding cache (LRU) for repeated identical queries (optional)

Error Handling:
    - API timeout: retry with exponential backoff (max 3 retries)
    - Rate limit (429): backoff and retry
    - Invalid input: raise EmbeddingError with details

Dependencies:
    - openai (AsyncOpenAI client)
    - app.models.chunk (Chunk)
    - app.config (OpenAISettings)
"""
