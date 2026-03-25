"""
Vector Store Abstract Interface
=================================

Purpose:
    Defines the abstract contract that all vector store implementations
    must satisfy. This abstraction allows the system to swap between
    FAISS and ChromaDB (or future backends) without changing any
    upstream code.

Interface Methods:

    add_chunks(chunks: list[Chunk]) -> None:
        Stores chunk embeddings and metadata in the vector database.
        Inputs:
            chunks: list of Chunk objects with embedding field populated
        Effects:
            - Vectors indexed for similarity search
            - Metadata stored for filtering and retrieval
        Raises:
            VectorStoreError if storage fails

    search(
        query_embedding: list[float],
        top_k: int,
        document_ids: list[str] | None = None
    ) -> list[tuple[Chunk, float]]:
        Performs nearest-neighbor similarity search.
        Inputs:
            query_embedding: 1536-dim query vector
            top_k: number of results to return
            document_ids: optional filter — only search within these documents
        Outputs:
            list of (Chunk, similarity_score) tuples, sorted by score descending
        Raises:
            VectorStoreError if search fails

    delete_document(document_id: str) -> int:
        Removes all vectors associated with a document.
        Inputs: document_id to remove
        Outputs: number of vectors removed
        Raises: VectorStoreError if deletion fails

    get_collection_stats() -> dict:
        Returns metadata about the vector store:
            - total_vectors: int
            - total_documents: int
            - index_type: str
            - dimensions: int

Vector Metadata Schema:
    Each vector is stored with this metadata dict:
    {
        "chunk_id": str,          # UUID
        "document_id": str,       # UUID — enables document-scoped search
        "document_name": str,     # original filename — for citations
        "chunk_index": int,       # position in document
        "page_numbers": list[int],# pages this chunk spans
        "token_count": int,       # for context budget calculations
        "text": str               # original chunk text — returned at search time
    }

Design Notes:
    - The interface is async-compatible (implementations may be sync internally
      but are wrapped in asyncio.to_thread for non-blocking usage)
    - Metadata filtering by document_id is critical for session-scoped retrieval
    - Text is stored in metadata (not just the vector) so retrieval returns
      complete chunks without a separate lookup

Dependencies:
    - abc (ABC, abstractmethod)
    - app.models.chunk (Chunk)
"""
