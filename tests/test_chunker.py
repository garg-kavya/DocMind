"""
Chunker Tests
==============

Purpose:
    Tests for the document chunking service. Validates chunk sizes,
    overlap behavior, boundary handling, and metadata accuracy.

Test Cases:

    test_chunk_sizes_within_budget:
        Assert all chunks have token_count <= CHUNK_SIZE_TOKENS.

    test_chunk_overlap:
        Assert that consecutive chunks share CHUNK_OVERLAP_TOKENS of text
        at their boundaries.

    test_paragraph_boundary_splitting:
        Given text with clear paragraph breaks, assert chunks split at
        paragraph boundaries rather than mid-sentence.

    test_sentence_boundary_fallback:
        Given a single long paragraph exceeding chunk size, assert it
        splits at sentence boundaries.

    test_page_number_tracking:
        Assert that chunks near page boundaries have correct page_numbers
        (may span two pages).

    test_chunk_index_sequential:
        Assert chunk_index values are 0, 1, 2, ... in order.

    test_character_offsets:
        Assert start_char_offset and end_char_offset correctly index
        back into the original document text.

    test_empty_text:
        Assert empty input produces empty chunk list (no crash).

    test_very_short_document:
        Assert a document shorter than one chunk produces exactly one chunk.

    test_document_id_propagation:
        Assert document_id and document_name are set on all chunks.

Dependencies:
    - pytest
    - app.services.chunker
    - app.utils.token_counter
"""
