"""
Retrieval Service
==================

Purpose:
    Performs semantic search over the vector database to find the most
    relevant document chunks for a given query. This is the core of the
    RAG pipeline's "R" (Retrieval).

Pipeline Position:
    User Question -> Reformulate -> Embed -> **Retrieve** -> Rank -> Generate

Retrieval Strategy (3-Stage Pipeline):

    Stage 1: Candidate Retrieval (Vector Similarity)
        - Embed the query via EmbeddingService.embed_query()
        - Search vector DB for top-k * 2 nearest neighbors (over-fetch)
        - Uses cosine similarity (vectors are pre-normalized)
        - Document-scoped: filters by document_ids in the session
        - Latency: ~10-50ms for FAISS, ~50-100ms for ChromaDB

    Stage 2: Score Threshold Filtering
        - Discard any chunk with similarity score < SIMILARITY_THRESHOLD (0.70)
        - Prevents low-relevance chunks from reaching the LLM even if fewer
          than top-k chunks remain
        - Threshold is calibrated: 0.70 with text-embedding-3-small provides
          a good precision/recall balance for factual PDF content

    Stage 3: MMR Re-Ranking (Maximal Marginal Relevance)
        - From the filtered candidates, select the final top-k using MMR
        - MMR balances relevance with diversity:
          score(chunk) = lambda * similarity(chunk, query)
                       - (1 - lambda) * max(similarity(chunk, already_selected))
        - lambda (MMR_DIVERSITY_FACTOR): 0.7 (favor relevance, mild diversity)
        - Effect: avoids returning 5 chunks that all say the same thing from
          different pages; instead returns 5 chunks that cover different
          aspects of the answer

Top-K Tuning Rationale:
    Default: top_k = 5

    - k=3: Suitable for simple factual lookups ("What is X?"). Minimal
      context, fast, but may miss supporting evidence.
    - k=5: Default. Covers most question types. 5 chunks of 512 tokens =
      ~2560 tokens of context, leaving ample room in a 4K budget for the
      prompt template, conversation history, and generated answer.
    - k=7-10: For complex analytical questions requiring synthesis across
      multiple sections. Uses more context window but provides broader
      coverage.
    - Configurable per-query via the API's top_k parameter.

Inputs:
    query_embedding: list[float]
        The embedded query vector (1536 dimensions).

    document_ids: list[str]
        Scope retrieval to these documents only.

    top_k: int
        Number of final chunks to return (after re-ranking).

Outputs:
    RetrievedContext:
        - chunks: list[ScoredChunk] — ranked chunks with scores
        - retrieval_metadata: dict with diagnostics:
            - retrieval_time_ms: float
            - candidates_considered: int
            - candidates_after_threshold: int
            - mmr_applied: bool
            - similarity_scores: list[float]

Dependencies:
    - app.db.vector_store (VectorStore interface)
    - app.services.embedder (EmbeddingService)
    - app.models.query (RetrievedContext, ScoredChunk)
    - app.config (RetrievalSettings)
"""
