"""
Query Reformulation Service
=============================

Purpose:
    Resolves conversational follow-up questions into standalone queries
    that can be used for effective semantic retrieval. This is critical
    for multi-turn Q&A where follow-ups reference prior context.

Problem:
    Follow-up questions often contain pronouns, ellipsis, and implicit
    references that make them meaningless without conversation history:

    Turn 1: "What was Acme Corp's revenue in Q3 2024?"
    Turn 2: "How does that compare to the previous quarter?"
    Turn 3: "What about their competitor?"

    "that", "the previous quarter", "their competitor" are unresolvable
    without context. Embedding these raw queries would retrieve irrelevant
    chunks.

Solution:
    Use the LLM to reformulate follow-ups into standalone questions:

    Turn 2 reformulated: "How does Acme Corp's Q3 2024 revenue compare
                          to Q2 2024 revenue?"
    Turn 3 reformulated: "What was the revenue of Acme Corp's competitor
                          in Q3 2024?"

Reformulation Prompt (Conceptual):
    "Given the following conversation history and a follow-up question,
    reformulate the follow-up into a standalone question that contains
    all necessary context for retrieval. Do not answer the question —
    only reformulate it.

    Conversation history:
    {history}

    Follow-up question: {question}

    Standalone question:"

Optimization:
    - First-turn questions (no history) skip reformulation entirely
    - Reformulation uses a fast model (gpt-4o-mini) to minimize latency
    - Typical reformulation latency: 200-400ms
    - Result is cached per (session_id, turn_index) to avoid recomputation

Methods:

    reformulate(
        query: str,
        conversation_history: list[ConversationTurn]
    ) -> str:
        Inputs:
            query: the user's raw follow-up question
            conversation_history: prior turns in this session
        Outputs:
            standalone_query: str — the reformulated question
        Returns the original query unchanged if history is empty.

Dependencies:
    - openai (AsyncOpenAI)
    - app.models.session (ConversationTurn)
    - app.config (OpenAISettings)
"""
