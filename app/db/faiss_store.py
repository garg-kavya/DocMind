"""
FAISS Vector Store Implementation
====================================

Purpose:
    Implements the VectorStore interface using Facebook AI Similarity Search
    (FAISS). Optimized for fast in-memory similarity search with optional
    disk persistence.

Why FAISS:
    - Fastest similarity search for datasets up to ~1M vectors
    - In-memory operation eliminates network latency
    - ~10-50ms search latency for typical PDF workloads
    - Supports multiple index types for different scale/speed tradeoffs

Index Configuration:
    - Default: IndexFlatIP (Inner Product on normalized vectors = cosine similarity)
      Best for datasets < 100K vectors (typical for PDF Q&A workloads)
    - Scale option: IndexIVFFlat with nlist=100 for datasets > 100K vectors
      Trades ~5% recall for 10x search speed

Metadata Storage:
    FAISS stores only vectors, not metadata. This implementation maintains
    a parallel dict mapping FAISS internal IDs to Chunk metadata:
    {
        faiss_id (int): {
            "chunk_id": str,
            "document_id": str,
            "document_name": str,
            "chunk_index": int,
            "page_numbers": list[int],
            "token_count": int,
            "text": str
        }
    }

Document Filtering:
    Since FAISS doesn't support metadata filtering natively:
    1. Over-fetch: retrieve top_k * 3 results
    2. Post-filter: keep only chunks matching document_ids
    3. Truncate to requested top_k

    For small document sets this is efficient. For large-scale deployments,
    consider per-document FAISS indices or switching to ChromaDB.

Persistence:
    - faiss.write_index() / faiss.read_index() for vector data
    - JSON serialization for metadata dict
    - Persistence directory: configurable, default ./data/faiss/

Methods:
    Implements all VectorStore interface methods plus:

    save_to_disk(path: str) -> None:
        Persists index and metadata to disk.

    load_from_disk(path: str) -> None:
        Loads previously persisted index and metadata.

Dependencies:
    - faiss-cpu (or faiss-gpu)
    - numpy
    - json
    - app.db.vector_store (VectorStore ABC)
    - app.models.chunk (Chunk)
"""
