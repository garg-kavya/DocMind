"""
Token Counting Utility
=======================

Purpose:
    Provides accurate token counting using tiktoken, the same tokenizer
    used by OpenAI models. Accurate token counts are essential for:
    - Chunk size enforcement (512-token target)
    - Context window budget management
    - Cost estimation

Functions:

    count_tokens(text: str, model: str = "cl100k_base") -> int:
        Counts tokens in a text string.
        Inputs:
            text: string to tokenize
            model: tiktoken encoding name (cl100k_base for GPT-4/embeddings)
        Outputs:
            integer token count

    truncate_to_tokens(text: str, max_tokens: int) -> str:
        Truncates text to fit within a token budget.
        Inputs:
            text: string to truncate
            max_tokens: maximum allowed tokens
        Outputs:
            truncated string (may be shorter than input)

    estimate_chunk_count(text: str, chunk_size: int, overlap: int) -> int:
        Estimates how many chunks a document will produce.
        Inputs:
            text: full document text
            chunk_size: tokens per chunk
            overlap: overlap tokens
        Outputs:
            estimated chunk count

Caching:
    The tiktoken encoding is loaded once and cached (module-level) to avoid
    repeated initialization overhead.

Dependencies:
    - tiktoken
"""
