# Architecture — RAG PDF Q&A System

## Overview

This system is a **production-grade Retrieval-Augmented Generation (RAG) pipeline** purpose-built for answering questions over uploaded PDF documents with conversational memory and source citations.

It is **not** a generic chatbot. Every component is designed around the constraint that answers must be grounded exclusively in the content of uploaded PDFs.

---

## High-Level Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                         CLIENT (Browser / API)                   │
│                                                                  │
│   Upload PDF ──────┐                    Ask Question ─────┐      │
│                    │                                      │      │
└────────────────────┼──────────────────────────────────────┼──────┘
                     │                                      │
                     ▼                                      ▼
┌──────────────────────────────┐   ┌───────────────────────────────┐
│     INGESTION PIPELINE       │   │       QUERY PIPELINE          │
│                              │   │                               │
│  ┌────────────────────────┐  │   │  ┌─────────────────────────┐  │
│  │   1. PDF Processor     │  │   │  │  1. Query Reformulator  │  │
│  │   (PyMuPDF/pdfplumber) │  │   │  │  (resolve follow-ups)   │  │
│  └──────────┬─────────────┘  │   │  └──────────┬──────────────┘  │
│             ▼                │   │             ▼                  │
│  ┌────────────────────────┐  │   │  ┌─────────────────────────┐  │
│  │   2. Text Cleaner      │  │   │  │  2. Embedder            │  │
│  │   (normalize/clean)    │  │   │  │  (query -> vector)      │  │
│  └──────────┬─────────────┘  │   │  └──────────┬──────────────┘  │
│             ▼                │   │             ▼                  │
│  ┌────────────────────────┐  │   │  ┌─────────────────────────┐  │
│  │   3. Chunker           │  │   │  │  3. Retriever           │  │
│  │   (512 tokens, overlap)│  │   │  │  (search + MMR rerank)  │  │
│  └──────────┬─────────────┘  │   │  └──────────┬──────────────┘  │
│             ▼                │   │             ▼                  │
│  ┌────────────────────────┐  │   │  ┌─────────────────────────┐  │
│  │   4. Embedder          │  │   │  │  4. Generator           │  │
│  │   (batch embed chunks) │  │   │  │  (LLM + citations)      │  │
│  └──────────┬─────────────┘  │   │  └──────────┬──────────────┘  │
│             ▼                │   │             ▼                  │
│  ┌────────────────────────┐  │   │  ┌─────────────────────────┐  │
│  │   5. Vector Store      │  │   │  │  5. Streaming Handler   │  │
│  │   (FAISS / ChromaDB)   │  │   │  │  (SSE token delivery)   │  │
│  └────────────────────────┘  │   │  └─────────────────────────┘  │
│                              │   │                               │
└──────────────────────────────┘   └───────────────────────────────┘
                     │                          │
                     ▼                          ▼
          ┌──────────────────────────────────────────┐
          │             SHARED STATE                  │
          │                                          │
          │  ┌────────────┐   ┌───────────────────┐  │
          │  │ Vector DB  │   │  Session Store    │  │
          │  │ (FAISS/    │   │  (in-memory,      │  │
          │  │  ChromaDB) │   │   TTL-expiring)   │  │
          │  └────────────┘   └───────────────────┘  │
          └──────────────────────────────────────────┘
```

---

## Component Breakdown

### 1. API Layer (`app/api/`)

**Framework:** FastAPI (async, OpenAPI docs, dependency injection)

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/v1/documents/upload` | POST | Upload and ingest a PDF |
| `/api/v1/documents/{id}` | GET | Check document processing status |
| `/api/v1/documents/{id}` | DELETE | Remove document and its vectors |
| `/api/v1/query` | POST | Ask a question (full response) |
| `/api/v1/query/stream` | POST | Ask a question (SSE streaming) |
| `/api/v1/sessions` | POST | Create a conversation session |
| `/api/v1/sessions/{id}` | GET | Get session details + history |
| `/api/v1/sessions/{id}` | DELETE | End a session |
| `/api/v1/health` | GET | Service health check |

**Middleware:**
- Rate limiting (token bucket per client IP)
- Global error handler (structured JSON error responses)
- CORS (configurable origins)

### 2. PDF Processing Pipeline (`app/services/pdf_processor.py`, `text_cleaner.py`, `chunker.py`)

**Parser:** Dual-engine with automatic fallback
- **Primary:** PyMuPDF (fitz) — ~100 pages/sec, handles most PDFs
- **Fallback:** pdfplumber — better for tables and complex layouts
- **Quality gate:** If both yield insufficient text, report error (scanned PDF)

**Cleaner:** 6-stage text normalization
- Unicode NFKC normalization
- Whitespace consolidation
- Hyphenated line-break rejoining
- Header/footer detection and removal
- Control character stripping
- Empty line consolidation

**Chunker:** Recursive character splitting
- **Size:** 512 tokens (configurable 256-1024)
- **Overlap:** 64 tokens (12.5%)
- **Hierarchy:** paragraphs → lines → sentences → words
- **Metadata:** page numbers, character offsets, token counts

### 3. Embedding Layer (`app/services/embedder.py`)

- **Model:** OpenAI `text-embedding-3-small` (1536 dimensions)
- **Ingestion:** Batch embedding (100 chunks/call) with async concurrency
- **Query:** Single embedding call (~100-150ms)
- **Error handling:** Exponential backoff on rate limits

### 4. Vector Storage (`app/db/`)

**Abstract interface** (`vector_store.py`) with two implementations:

| Feature | FAISS | ChromaDB |
|---|---|---|
| Search latency | ~10-50ms | ~50-100ms |
| Metadata filtering | Post-filter (over-fetch) | Native WHERE clause |
| Persistence | Manual save/load | Automatic |
| Best for | Performance-critical prod | Rapid development |

**Metadata per vector:** chunk_id, document_id, document_name, chunk_index, page_numbers, token_count, text

### 5. Retrieval System (`app/services/retriever.py`)

3-stage retrieval pipeline:
1. **Vector search:** Cosine similarity, top-k×2 candidates
2. **Score threshold:** Discard chunks below 0.70 similarity
3. **MMR re-ranking:** Balance relevance with diversity (λ=0.7)

### 6. Answer Generation (`app/services/generator.py`)

- **Model:** GPT-4o (temperature=0.1)
- **Prompt:** System instruction enforcing context-only answers with [Source N] citations
- **Citation extraction:** Post-processing parses source references and maps to chunk metadata
- **Confidence scoring:** Heuristic based on retrieval scores and citation density

### 7. Conversational Memory (`app/db/session_store.py`)

- **Storage:** In-memory dict with TTL-based expiry (default 60 min)
- **History:** Last 10 turns per session (configurable)
- **Follow-ups:** Query reformulation via LLM resolves pronouns and references
- **Cleanup:** Background task purges expired sessions every 5 minutes

### 8. Streaming (`app/services/streaming.py`)

- **Protocol:** Server-Sent Events (SSE)
- **Flow:** Retrieval completes first (blocking), then generation streams token-by-token
- **Events:** `token` → `citation` → `done` (or `error`)
- **Cancellation:** Client disconnect stops generation (saves API cost)

---

## Design Decisions

### Why 512-token chunks?
See `docs/retrieval_strategy.md` for the full analysis. In short: 512 balances precision (small enough for focused relevance) with context (large enough for coherent ideas). 5 chunks × 512 tokens = 2560 tokens, fitting in a 4K context budget.

### Why in-memory session storage?
Sessions are ephemeral (1-hour TTL), small (10 turns), and accessed in the hot path. In-memory provides sub-millisecond reads. For horizontal scaling, swap to Redis via the same SessionStore interface.

### Why FAISS + ChromaDB abstraction?
FAISS is fastest for production but lacks native metadata filtering. ChromaDB is simpler for development. The abstraction layer lets teams choose per-environment.

### Why dual PDF parsers?
No single parser handles all PDF variants well. PyMuPDF is fast but struggles with complex layouts. pdfplumber handles edge cases but is slower. The fallback strategy gets the best of both.

---

## Scalability Path

| Scale | Storage | Sessions | Deployment |
|---|---|---|---|
| Dev/POC | FAISS (in-memory) | In-memory dict | Single container |
| Small prod | ChromaDB (persistent) | Redis | Docker Compose |
| Large prod | Pinecone/Weaviate | Redis Cluster | Kubernetes |
