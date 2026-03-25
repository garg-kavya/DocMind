"""
Database / Storage Layer
=========================

Provides vector storage and session storage abstractions:

    vector_store   -> Abstract interface for vector DB operations
    faiss_store    -> FAISS implementation (in-memory, fast)
    chroma_store   -> ChromaDB implementation (persistent, metadata-rich)
    session_store  -> In-memory session storage with TTL cleanup
"""
