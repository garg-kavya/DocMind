"""
Chunk Domain Model
===================

Purpose:
    Represents a single text chunk extracted from a PDF document. Chunks are
    the atomic unit of retrieval — each chunk is independently embedded and
    stored as a vector in the vector database.

Attributes:
    chunk_id: str (UUID4)
        Unique identifier for this chunk.

    document_id: str (UUID4)
        Foreign key linking back to the parent Document.

    document_name: str
        Original filename for citation display (avoids joins at query time).

    chunk_index: int
        Zero-based sequential position of this chunk within the document.
        Used for ordering and context window reconstruction.

    text: str
        The actual text content of this chunk after cleaning.

    token_count: int
        Number of tokens in this chunk (measured via tiktoken cl100k_base).

    page_numbers: list[int]
        List of page numbers this chunk spans. A chunk near a page boundary
        may span two pages (e.g., [3, 4]).

    start_char_offset: int
        Character offset from the beginning of the full document text where
        this chunk starts. Enables precise source location.

    end_char_offset: int
        Character offset where this chunk ends.

    embedding: list[float] | None
        The embedding vector (1536 dimensions for text-embedding-3-small).
        None before embedding is computed; populated during the embedding
        pipeline step.

    metadata: dict
        Additional metadata stored alongside the vector:
        - document_id, document_name, chunk_index, page_numbers, token_count
        This dict is what gets stored in the vector DB metadata field.

Design Decisions:
    - Chunk size of 512 tokens with 64-token overlap is configured in
      app.config.ChunkingSettings. See that module for rationale.
    - page_numbers is a list (not single int) because semantic chunking
      at paragraph boundaries can cross page breaks.
    - document_name is denormalized onto the chunk to avoid a join when
      constructing citations at response time.

Dependencies:
    - uuid
    - dataclasses or attrs
"""
