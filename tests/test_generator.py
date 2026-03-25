"""
Generator Tests
================

Purpose:
    Tests for the LLM answer generation and citation extraction service.

Test Cases:

    test_answer_grounded_in_context:
        Given context chunks, assert the generated answer references
        information present in those chunks.

    test_citation_extraction:
        Assert that [Source N] references in the answer are correctly
        parsed into structured Citation objects.

    test_citation_validation:
        Assert that citations referencing non-existent source numbers
        are flagged or removed.

    test_no_context_response:
        When retrieved chunks are empty, assert the response indicates
        "information not found" rather than hallucinating.

    test_confidence_scoring:
        Assert confidence is higher for well-matched context and lower
        for marginal matches.

    test_streaming_token_output:
        Assert generate_stream() yields individual tokens as async events.

    test_conversation_history_in_prompt:
        Assert prior turns are included in the generation prompt.

    test_context_truncation:
        When total context exceeds the LLM's window, assert lowest-scored
        chunks are dropped.

Dependencies:
    - pytest
    - pytest-asyncio
    - app.services.generator
    - app.chains.prompts
    - unittest.mock (for OpenAI API mocking)
"""
