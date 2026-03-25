"""
Answer Generation Service
==========================

Purpose:
    Generates natural language answers grounded in retrieved document chunks,
    with structured citations. This is the final stage of the RAG pipeline.

Pipeline Position:
    User Question -> Reformulate -> Embed -> Retrieve -> Rank -> **Generate**

LLM Configuration:
    Model: gpt-4o (configurable)
    Temperature: 0.1 (low — factual, grounded responses)
    Max tokens: 1024 (sufficient for detailed answers with citations)

Prompt Design (Conceptual):

    System Prompt:
        "You are a document question-answering assistant. Your answers must
        be grounded EXCLUSIVELY in the provided source context. Do not use
        prior knowledge. If the context does not contain enough information
        to answer the question, explicitly state that.

        When referencing information from the context, cite the source using
        the format [Source N] where N corresponds to the numbered context
        chunks below. Always cite your sources."

    Context Block:
        "[Source 1] (report.pdf, Page 5, Chunk 12)
         <chunk text here>

         [Source 2] (report.pdf, Page 8, Chunk 23)
         <chunk text here>

         [Source 3] (financials.pdf, Page 2, Chunk 4)
         <chunk text here>"

    Conversation History (if multi-turn):
        Prior Q&A turns for continuity.

    User Question:
        The standalone (reformulated) query.

Citation Extraction:
    After LLM generation, the service:
    1. Parses [Source N] references in the answer text
    2. Maps each reference back to the corresponding chunk metadata
    3. Builds structured Citation objects with:
       - document_name, page_numbers, chunk_index, chunk_id, excerpt
    4. Validates that all citations reference chunks that were actually
       provided in the context (hallucination guard)

Confidence Scoring:
    Heuristic confidence based on:
    - Mean similarity score of retrieved chunks (higher = more relevant context)
    - Whether the LLM explicitly stated uncertainty
    - Number of distinct sources cited (more sources = higher confidence)
    Score: 0.0 (no relevant context found) to 1.0 (high-confidence answer)

Methods:

    generate(query: QueryContext, context: RetrievedContext) -> GeneratedAnswer:
        Synchronous (non-streaming) answer generation.
        Inputs: reformulated query + retrieved chunks
        Outputs: GeneratedAnswer with text, citations, confidence

    generate_stream(query: QueryContext, context: RetrievedContext) -> AsyncGenerator:
        Streaming variant that yields tokens as they're generated.
        Inputs: same as generate()
        Outputs: async generator of StreamingChunk events

Error Handling:
    - LLM timeout: retry once, then return error response
    - Context too long: truncate lowest-scored chunks to fit context window
    - Refusal: if LLM refuses, return with confidence=0 and explanation

Dependencies:
    - openai (AsyncOpenAI, ChatCompletion)
    - app.models.query (QueryContext, RetrievedContext, GeneratedAnswer, Citation)
    - app.chains.prompts (prompt templates)
    - app.config (OpenAISettings)
"""
