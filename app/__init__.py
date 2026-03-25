"""
RAG PDF Q&A Application
========================

A production-grade Retrieval-Augmented Generation system specifically designed
for PDF document question answering with conversational memory.

This package provides:
    - PDF ingestion and intelligent chunking
    - Semantic embedding and vector storage
    - Context-aware retrieval with citation tracking
    - LLM-powered answer generation grounded in document content
    - Multi-turn conversational Q&A with session management
    - Low-latency streaming responses via Server-Sent Events

Architecture Overview:
    PDF Upload -> Parse -> Clean -> Chunk -> Embed -> Store (Vector DB)
    User Query -> Reformulate -> Embed -> Retrieve -> Rank -> Generate -> Stream

Tech Stack:
    - FastAPI (async web framework)
    - LangChain / LangGraph (orchestration)
    - OpenAI API (embeddings + LLM)
    - FAISS / ChromaDB (vector storage)
    - PyMuPDF / pdfplumber (PDF parsing)
"""

__version__ = "0.1.0"
