"""
Document Chunking Service
==========================

Purpose:
    Splits cleaned document text into semantically coherent chunks optimized
    for embedding and retrieval. This is the third stage of the ingestion
    pipeline: Upload -> Parse -> Clean -> **Chunk** -> Embed -> Store.

Chunking Strategy: Recursive Character Splitting with Semantic Awareness

    The chunker uses a hierarchical separator strategy to split text at the
    most semantically meaningful boundary that keeps chunks within the
    configured token budget:

    Split Hierarchy (tried in order):
        1. "\\n\\n" — Paragraph breaks (strongest semantic boundary)
        2. "\\n"   — Line breaks
        3. ". "    — Sentence boundaries
        4. " "     — Word boundaries (last resort)

    This ensures chunks respect natural document structure. A paragraph is
    never split mid-sentence unless it exceeds the token limit on its own.

Chunk Size Justification:

    Default: 512 tokens, configurable range 256-1024.

    Why 512 is the sweet spot for PDF Q&A:
    - 256 tokens: Too granular. Paragraphs get split mid-thought, losing
      the context needed for accurate retrieval. Precision@5 drops because
      relevant information is scattered across too many small fragments.
    - 512 tokens: ~1-2 paragraphs. Large enough to contain a coherent idea
      with supporting detail. Small enough that the relevance signal isn't
      diluted by unrelated content. 5 chunks of 512 tokens = 2560 tokens,
      fitting comfortably in a 4K context budget alongside the prompt,
      conversation history, and generation space.
    - 1024 tokens: Too broad. Chunks contain multiple topics, reducing
      precision. The embedding becomes a blurred average of mixed content.
      Fewer chunks fit in the LLM context window, limiting coverage.

    Overlap: 64 tokens (12.5% of chunk size)
    - Prevents information loss at chunk boundaries
    - A sentence at the edge of chunk N is also present at the start of
      chunk N+1, ensuring retrieval can find it regardless of which chunk
      the query matches
    - 12.5% is low enough to avoid excessive storage/embedding overhead

Inputs:
    cleaned_text: str
        Full cleaned document text.

    document_id: str
        UUID of the parent document.

    document_name: str
        Original filename (denormalized onto each chunk for citations).

    page_boundaries: list[int]
        Character offsets where page breaks occur. Used to assign accurate
        page_numbers to each chunk.

Outputs:
    chunks: list[Chunk]
        Ordered list of Chunk domain objects, each with:
        - chunk_id, document_id, document_name, chunk_index
        - text, token_count, page_numbers
        - start_char_offset, end_char_offset

Token Counting:
    Uses tiktoken with cl100k_base encoding (same tokenizer as OpenAI
    embedding and chat models) for accurate token measurement.

Dependencies:
    - tiktoken
    - app.models.chunk (Chunk)
    - app.config (ChunkingSettings)
"""
