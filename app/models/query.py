"""
Query and Response Domain Models
==================================

Purpose:
    Internal representations of a user query and the system's response.
    These models flow through the RAG chain and carry accumulated context
    from retrieval through generation.

Models:

    QueryContext:
        The enriched query object that flows through the RAG pipeline.

        Attributes:
            raw_query: str
                The user's original question as received from the API.
            standalone_query: str
                The reformulated query after conversational context resolution.
                For first-turn questions, this equals raw_query. For follow-ups,
                this resolves pronouns and references (e.g., "What about its
                revenue?" -> "What is Acme Corp's revenue in Q3 2024?").
            session_id: str
                The session this query belongs to.
            document_ids: list[str]
                Documents to scope retrieval to.
            conversation_history: list[ConversationTurn]
                Prior turns for context.
            query_embedding: list[float] | None
                The embedding of standalone_query, populated by the embedder.

    RetrievedContext:
        The set of chunks retrieved for a query.

        Attributes:
            chunks: list[ScoredChunk]
                Ranked list of chunks with similarity scores.
            retrieval_metadata: dict
                Diagnostics: retrieval_time_ms, candidates_considered,
                threshold_applied, mmr_applied.

    ScoredChunk:
        A chunk paired with its retrieval score.

        Attributes:
            chunk: Chunk
                The chunk domain object.
            similarity_score: float
                Cosine similarity score (0.0 to 1.0).
            rank: int
                Position in the final ranked list (1-based).

    GeneratedAnswer:
        The final response produced by the system.

        Attributes:
            answer_text: str
                The LLM-generated answer grounded in retrieved context.
            citations: list[Citation]
                Structured source references extracted from the answer.
            confidence: float
                Heuristic confidence based on retrieval scores and
                answer coherence (0.0 to 1.0).
            retrieval_context: RetrievedContext
                The full retrieval result for transparency/debugging.

    Citation:
        A single source reference within an answer.

        Attributes:
            document_name: str
                Original PDF filename.
            page_numbers: list[int]
                Pages where the cited information appears.
            chunk_index: int
                Chunk position in the document.
            chunk_id: str
                Unique chunk identifier.
            excerpt: str
                Short excerpt from the chunk that supports the citation.

Dependencies:
    - dataclasses
    - app.models.chunk (Chunk)
    - app.models.session (ConversationTurn)
"""
