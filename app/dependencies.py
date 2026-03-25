"""
FastAPI Dependency Injection
=============================

Purpose:
    Provides FastAPI dependency functions that inject shared service instances
    into route handlers. This module acts as the composition root, wiring
    together services, stores, and configuration into a cohesive dependency
    graph.

Dependencies Provided:

    get_settings() -> Settings:
        Returns the validated application settings singleton.

    get_vector_store() -> VectorStore:
        Returns the configured vector store instance (FAISS or ChromaDB)
        based on settings.VECTOR_STORE_TYPE. Initialized once at startup.

    get_embedder() -> EmbeddingService:
        Returns the embedding service configured with the OpenAI API key
        and model settings.

    get_pdf_processor() -> PDFProcessorService:
        Returns the PDF processing pipeline (parser + cleaner + chunker).

    get_retriever() -> RetrieverService:
        Returns the retrieval service wired to the vector store and embedder.

    get_generator() -> GeneratorService:
        Returns the LLM generation service configured with prompts and
        citation formatting.

    get_session_store() -> SessionStore:
        Returns the in-memory session store for conversational memory.

    get_rag_chain() -> RAGChain:
        Returns the fully assembled RAG chain that orchestrates:
        query reformulation -> retrieval -> generation.

Lifecycle:
    - Services are instantiated during app startup (lifespan context)
    - Stored as app.state attributes
    - Dependency functions read from app.state via request.app.state
    - Shutdown triggers cleanup (connection close, state flush)

Inputs:
    - FastAPI Request object (for accessing app.state)
    - app.config.Settings

Outputs:
    - Configured service instances for route handlers

Dependencies:
    - fastapi (Depends, Request)
    - app.config
    - app.services.* (all service modules)
    - app.db.* (all store modules)
"""
