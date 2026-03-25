"""
ChromaDB Vector Store Implementation
=======================================

Purpose:
    Implements the VectorStore interface using ChromaDB. Provides built-in
    metadata filtering, persistence, and a simpler API at the cost of
    slightly higher search latency compared to FAISS.

Why ChromaDB:
    - Native metadata filtering (no post-filtering needed)
    - Built-in persistence to disk
    - Simpler operational model (no separate metadata dict)
    - Better developer experience for prototyping and small-scale deployments
    - ~50-100ms search latency (acceptable for <2s target)

Collection Schema:
    Collection name: "pdf_chunks" (configurable)

    Each document in the collection:
        id: str = chunk_id (UUID)
        embedding: list[float] (1536 dimensions)
        document: str = chunk text
        metadata: {
            "document_id": str,
            "document_name": str,
            "chunk_index": int,
            "page_numbers": str,  # JSON-serialized list (ChromaDB metadata
                                  # doesn't support list values natively)
            "token_count": int
        }

Document-Scoped Search:
    ChromaDB supports metadata WHERE clauses natively:
        where={"document_id": {"$in": document_ids}}
    This is more efficient than FAISS post-filtering for multi-document sessions.

Persistence:
    - ChromaDB PersistentClient stores data at configurable path
    - Default: ./data/chroma/
    - Auto-persists on every write operation

Methods:
    Implements all VectorStore interface methods.
    ChromaDB handles persistence automatically — no explicit save/load needed.

Dependencies:
    - chromadb
    - app.db.vector_store (VectorStore ABC)
    - app.models.chunk (Chunk)
    - app.config (RetrievalSettings)
"""
