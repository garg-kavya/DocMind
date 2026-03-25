"""
RAG Orchestration Chain
========================

Purpose:
    The central orchestrator that wires together all RAG pipeline stages
    into a single callable chain. This is the entry point that API handlers
    invoke to process a user query end-to-end.

Execution Flow:

    1. Session Resolution
       - Load session from SessionStore
       - Validate session exists and has documents
       - Extract conversation history and document_ids

    2. Query Reformulation (conditional)
       - If conversation_history is non-empty:
         Call QueryReformulator to produce standalone_query
       - If first turn: standalone_query = raw_query
       - Latency: 0ms (first turn) or 200-400ms (follow-up)

    3. Query Embedding
       - Call EmbeddingService.embed_query(standalone_query)
       - Produces 1536-dim vector
       - Latency: ~100-150ms

    4. Retrieval
       - Call RetrieverService.retrieve() with embedding and document_ids
       - 3-stage pipeline: vector search -> threshold filter -> MMR re-rank
       - Returns top-k scored chunks
       - Latency: ~50-150ms

    5. Generation
       - Call GeneratorService.generate() or generate_stream()
       - Passes reformulated query + retrieved chunks + conversation history
       - Returns answer with citations
       - Latency: ~500-1500ms (non-streaming) or ~300-500ms to first token

    6. Session Update
       - Append new ConversationTurn to session history
       - Update last_active_at timestamp

    Total Latency Budget:
       Reformulation:  200-400ms (follow-up) or 0ms (first turn)
       Embedding:      100-150ms
       Retrieval:       50-150ms
       Generation:     300-500ms (first token, streaming)
       ────────────────────────────
       Total to first token: 650-1200ms (well under 2s target)

LangChain/LangGraph Integration:
    This chain can be implemented as:
    - A LangChain LCEL (LangChain Expression Language) chain
    - A LangGraph stateful graph with nodes for each stage
    - LangGraph is preferred for the conditional reformulation logic
      and built-in streaming support

Methods:

    invoke(query: str, session_id: str, **kwargs) -> GeneratedAnswer:
        Synchronous execution of the full pipeline.
        Inputs: raw query string + session ID
        Outputs: GeneratedAnswer with text, citations, confidence

    stream(query: str, session_id: str, **kwargs) -> AsyncGenerator:
        Streaming execution — retrieval is synchronous, generation streams.
        Inputs: same as invoke()
        Outputs: async generator of SSE events

Dependencies:
    - langchain / langgraph
    - app.services.query_reformulator
    - app.services.embedder
    - app.services.retriever
    - app.services.generator
    - app.db.session_store
    - app.models.query (QueryContext, RetrievedContext, GeneratedAnswer)
"""
