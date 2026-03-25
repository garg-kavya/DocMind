"""
LangChain / LangGraph Chains
==============================

Orchestration chains that wire together the RAG pipeline stages
into a coherent execution flow.

    rag_chain  -> Main orchestrator: reformulate -> embed -> retrieve -> generate
    prompts    -> Prompt templates for generation and reformulation
"""
