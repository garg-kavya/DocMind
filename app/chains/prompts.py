"""
Prompt Templates
=================

Purpose:
    Centralized prompt templates used by the generator and query reformulator.
    Keeping prompts in a dedicated module allows versioning, A/B testing,
    and easy iteration without touching service logic.

Templates:

    SYSTEM_PROMPT:
        The system-level instruction for the answer generation LLM.
        Key directives:
        - Answer ONLY from provided context (no prior knowledge)
        - Cite sources using [Source N] format
        - State clearly when information is not in the context
        - Be precise, factual, and concise

    CONTEXT_TEMPLATE:
        Formats retrieved chunks into a numbered source block.
        Format per chunk:
            "[Source {rank}] ({document_name}, Page {page_numbers}, Chunk {chunk_index})
             {chunk_text}"
        Chunks are ordered by relevance rank.

    QUERY_REFORMULATION_PROMPT:
        Instruction for converting follow-up questions into standalone queries.
        Includes conversation history formatting and clear directive:
        "Reformulate the follow-up into a self-contained question. Do not
        answer — only reformulate."

    CONVERSATION_HISTORY_TEMPLATE:
        Formats prior turns for injection into the generation prompt.
        Format per turn:
            "User: {user_query}
             Assistant: {assistant_response}"
        Limited to last N turns (configurable).

    NO_CONTEXT_RESPONSE:
        Template for when retrieval returns zero chunks above threshold.
        "I could not find relevant information in the uploaded documents
        to answer your question. Please try rephrasing or ensure the
        relevant document has been uploaded."

Design Principles:
    - Prompts are string templates with {variable} placeholders
    - Compatible with LangChain PromptTemplate / ChatPromptTemplate
    - No f-strings or hardcoded values — all parameterized
    - Each template has a docstring explaining its variables and usage

Dependencies:
    - langchain.prompts (PromptTemplate, ChatPromptTemplate) — optional
    - String formatting only (stdlib)
"""
