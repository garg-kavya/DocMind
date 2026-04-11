# Architecture — DocMind

## Overview

A production-grade Retrieval-Augmented Generation system for answering questions over uploaded PDF documents with conversational memory, source citations, and low-latency streaming.

Every answer is grounded exclusively in uploaded PDF content. No prior knowledge leaks from the LLM.

---

## Layer Model

```
┌────────────────────────────────────────────────────────────────────┐
│                    CLIENT  (React + Vite SPA)                      │
│  Dark GPT-style UI · Off-canvas mobile sidebar · SSE streaming     │
│  localStorage auth/session state · marked.js Markdown rendering    │
└───────────────┬────────────────────────────────┬───────────────────┘
                │                                │
                ▼                                ▼
┌────────────────────────────────────────────────────────────────────┐
│                    AUTH LAYER  (app/api/v1/auth.py)                │
│  POST /auth/register          POST /auth/login                     │
│  GET  /auth/google            GET  /auth/google/callback           │
│  POST /auth/forgot-password   POST /auth/reset-password            │
│  GET  /auth/me                POST /auth/logout                    │
│                                                                    │
│  bcrypt · python-jose JWT (HS256, 1-year TTL)                      │
│  UserStore (PostgreSQL) · TokenBlocklist (PostgreSQL)              │
│  PasswordResetStore (PostgreSQL) · Google OAuth 2.0 (optional)     │
└───────────────┬────────────────────────────────┬───────────────────┘
                │                                │
                ▼                                ▼
┌────────────────────────────────────────────────────────────────────┐
│                       API LAYER  (app/api/)                        │
│  /documents/upload   /documents/{id}   /documents                  │
│  /sessions           /sessions/{id}                                │
│  /query              /query/stream                                 │
│  /health             /debug/index      /debug/search               │
│                                                                    │
│  Token-bucket rate limiter (asyncio.Lock per user_id)              │
│  Session ownership enforcement (user_id checked on get/delete)     │
│  Thin handlers: validate → delegate → map response                 │
└───────────────┬────────────────────────────────┬───────────────────┘
                │                                │
                ▼                                ▼
┌──────────────────────────┐   ┌────────────────────────────────────┐
│  INGESTION PIPELINE      │   │  RAG PIPELINE  (app/pipeline/)     │
│  (app/pipeline/)         │   │                                    │
│                          │   │  cache check → reformulate →       │
│  PDF parse → clean       │   │  embed (cached) →                  │
│  → chunk → embed         │   │  hybrid retrieve (vector + FTS     │
│  → pgvector store        │   │  merged via RRF) → rerank →        │
│  → registry update       │   │  MMR → memory read →               │
│  Orphan cleanup on err   │   │  generate (cached) → memory write  │
└──────────────────────────┘   └────────────────────────────────────┘
                │                                │
                └────────────────┬───────────────┘
                                 │ calls
          ┌──────────────────────┼──────────────────────────┐
          │                      │                          │
          ▼                      ▼                          ▼
┌───────────────────┐  ┌──────────────────────┐  ┌──────────────────┐
│  SERVICES         │  │  CACHE LAYER         │  │  MEMORY LAYER    │
│  (app/services/)  │  │  (app/cache/)        │  │  (app/memory/)   │
│                   │  │                      │  │                  │
│  pdf_processor    │  │  EmbeddingCache      │  │  MemoryManager   │
│  text_cleaner     │  │   sha256(query)→24h  │  │   per-session    │
│  chunker          │  │                      │  │   asyncio.Lock   │
│  embedder         │  │  ResponseCache       │  │                  │
│  retriever        │  │   (session,query,    │  │  ContextBuilder  │
│  reranker         │  │    docs,turns)→60s   │  │   token-budgets  │
│  reformulator     │  │                      │  │                  │
│  streaming        │  └──────────────────────┘  │  MemoryCompressor│
└───────────────────┘                            └──────────────────┘
          │
          ▼
┌────────────────────────────────────────────────────────────────────┐
│  CHAINS LAYER  (app/chains/)                                       │
│  RAGChain — prompt assembly, OpenAI call, citation parse,          │
│             confidence scoring from normalised cosine similarity   │
│  prompts.py — system, context_block, history, reformulation        │
└────────────────────────────────────────────────────────────────────┘
          │
          ▼
┌──────────────────────┐   ┌────────────────────────────────────────┐
│  DB / STORAGE        │   │  DOMAIN MODELS (app/models/, schemas/) │
│  (app/db/)           │   │                                        │
│                      │   │  QueryContext, ScoredChunk             │
│  PGVectorStore  ◄────┤   │  GeneratedAnswer, PipelineMetadata     │
│  (pgvector + FTS,    │   │  ChunkMetadata, RetrievalMetadata      │
│   hybrid/RRF)        │   │  User, Session (user_id field)         │
│                      │   │  ConversationTurn, Citation            │
│  FAISSStore          │   └────────────────────────────────────────┘
│  SessionStore        │
│  DocumentRegistry    │         PostgreSQL tables
│  UserStore           │   ┌────────────────────────────────────────┐
│  TokenBlocklist      │──►│  users              (auth)             │
│  PasswordResetStore  │   │  token_blocklist    (logout/JWT)       │
└──────────────────────┘   │  password_resets    (reset flow)       │
                           │  document_chunks    (pgvector + FTS)   │
                           └────────────────────────────────────────┘
                                 JSON files (data/)
                           ┌────────────────────────────────────────┐
                           │  sessions.json   (SessionStore)        │
                           │  registry.json   (DocumentRegistry)    │
                           └────────────────────────────────────────┘
```

---

## Component Reference

### Auth Layer (`app/api/v1/auth.py`)

| Endpoint | Behaviour |
|---|---|
| `POST /auth/register` | bcrypt-hashes password; 409 if email exists or is linked to Google |
| `POST /auth/login` | Distinct errors: no account (404), Google-only account (400), wrong password (403) |
| `GET /auth/google` | Redirects to Google consent screen; returns 501 if `GOOGLE_CLIENT_ID` not set |
| `GET /auth/google/callback` | Exchanges OAuth code for token; creates or loads Google-linked user; redirects to frontend with JWT |
| `POST /auth/forgot-password` | Always returns 200 (no email enumeration); sends one-time link if SMTP configured |
| `POST /auth/reset-password` | Validates one-time token from `PasswordResetStore`; issues fresh JWT; token consumed on use |
| `GET /auth/me` | Returns `user_id`, `email`, `name`, `auth_provider` |
| `POST /auth/logout` | Adds JWT's JTI to `TokenBlocklist` with remaining TTL; token is blocked immediately |

`get_current_user` dependency (used by all protected routes):
1. Verifies JWT signature and expiry
2. Checks `TokenBlocklist` to reject logged-out tokens
3. Injects the `User` model into the handler

`TokenBlocklist` uses `datetime.now(timezone.utc)` (not the deprecated naive `datetime.utcnow()`) to avoid `TypeError` with asyncpg's `TIMESTAMPTZ` columns.

### API Layer (`app/api/`)

| Endpoint | Delegates to |
|---|---|
| `POST /documents/upload` | `IngestionPipeline.run()` as BackgroundTask; orphan file cleanup if registry raises |
| `GET /documents/{id}` | `DocumentRegistry.get()` |
| `DELETE /documents/{id}` | `VectorStore.delete_document()` + `DocumentRegistry.delete()` |
| `GET /documents` | `DocumentRegistry.get_all()` |
| `POST /sessions` | `SessionStore.create_session(user_id=current_user.user_id)` |
| `GET /sessions/{id}` | Ownership check → `SessionStore.get_session()` |
| `DELETE /sessions/{id}` | Ownership check → `SessionStore.delete_session()` |
| `POST /query` | `RAGPipeline.run()` |
| `POST /query/stream` | `RAGPipeline.run_stream()` → `StreamingHandler` SSE |
| `GET /health` | VectorStore stats + OpenAI ping + upload dir check |
| `GET /debug/index` | Index stats + registry doc list |
| `GET /debug/search` | Shared `app.state.embedder` → raw similarity scores |

**Rate limiter**: token-bucket per `user_id`. All bucket read-check-append operations are wrapped in `asyncio.Lock` to eliminate the TOCTOU race under concurrent async requests.

**Session ownership**: `Session.user_id` stored at creation. `get_session` and `delete_session` raise `SessionNotFoundError` (indistinguishable from not-found) when `session.user_id != current_user.user_id` — prevents session ID enumeration across users.

### Pipeline Layer (`app/pipeline/`)

**`rag_pipeline.py`** — single orchestrator. Services, caches, and memory modules are only ever called from here. The API layer does not call them directly.

**`ingestion_pipeline.py`** — single orchestrator for PDF processing. Runs as a FastAPI BackgroundTask. On any error after file save, the orphan file is removed via `os.unlink`.

### Services Layer (`app/services/`)

| Service | Responsibility |
|---|---|
| `pdf_processor` | PDF parsing: PyMuPDF → pdfplumber → Tesseract OCR (3-level fallback); garbled-text detection triggers auto-fallback |
| `text_cleaner` | Normalise extracted text: whitespace, ligatures, mojibake, hyphenation, control chars, line noise |
| `chunker` | Recursive character split: 512 tokens, 64-token overlap, boundary hierarchy `\n\n → \n → . → ` ` |
| `embedder` | Batch-embed via OpenAI `text-embedding-3-small` (100 chunks/batch); shared via `app.state.embedder` |
| `retriever` | Hybrid vector + FTS search → RRF merge → threshold filter → MMR selection |
| `reranker` | Optional cross-encoder / Cohere second-pass reranking; graceful fallback to bi-encoder order on error |
| `query_reformulator` | Runs on every query: coreference resolution + inference expansion |
| `streaming` | Wraps token generator as SSE; `X-Query-Id` header only set when `query_id` is available |

### Chains Layer (`app/chains/`)

| Module | Responsibility |
|---|---|
| `rag_chain.py` | Prompt assembly, OpenAI `gpt-4o` call (`temperature=0.1`), `[Source N]` citation extraction, confidence from normalised cosine similarity |
| `prompts.py` | All prompt templates: system, context_block, history, reformulation |

### Cache Layer (`app/cache/`)

| Cache | What is stored | Key | TTL |
|---|---|---|---|
| `EmbeddingCache` | 1536-dim query vectors | sha256(normalised query) | 24h |
| `ResponseCache` | Full `GeneratedAnswer` | sha256(session + query + docs + turn_count) | 60s |

### Memory Layer (`app/memory/`)

| Module | Responsibility |
|---|---|
| `MemoryManager` | Orchestrates history read/write; per-session `asyncio.Lock` makes the update→compress→replace sequence atomic, preventing concurrent turns from corrupting history |
| `ContextBuilder` | Serialises `ConversationTurn` list to a token-budgeted string (1024-token default); trims oldest turns first |
| `MemoryCompressor` | Summarises oldest N turns into a compressed summary when `turn_count` exceeds threshold |

### DB / Storage Layer (`app/db/`)

| Module | Backend | Responsibility |
|---|---|---|
| `PGVectorStore` | PostgreSQL + pgvector | Cosine similarity search (`<=>` operator) + PostgreSQL FTS (`ts_rank_cd`); hybrid merged via RRF |
| `FAISSStore` | FAISS `IndexFlatIP` | Optional in-process store; fetches all vectors when filtering by `document_id` |
| `ChromaStore` | ChromaDB | Legacy; not wired by default |
| `SessionStore` | `data/sessions.json` | Session CRUD + TTL expiry; persists `user_id` for ownership enforcement |
| `DocumentRegistry` | `data/registry.json` | Document status, metadata, ingestion results |
| `UserStore` | PostgreSQL via asyncpg | User CRUD; supports email/password and Google OAuth accounts |
| `TokenBlocklist` | PostgreSQL via asyncpg | Blocked JTI values + expiry; cleanup task runs in background loop |
| `PasswordResetStore` | PostgreSQL via asyncpg | One-time reset tokens with expiry |

**Active default**: `PGVectorStore` (wired in `app/dependencies.py`). Same PostgreSQL instance as user/auth data — one `DATABASE_URL` covers everything.

---

## Frontend (React + Vite SPA)

Built by Vite, output to `app/frontend/`, served as static files by FastAPI. SPA catch-all: unknown routes return `index.html` via the 404 handler.

| File | Role |
|---|---|
| `frontend/src/api.js` | `apiFetch` wrapper: auth headers, error normalisation, 401 silent redirect |
| `frontend/src/store.js` | localStorage persistence: sessions, auth tokens |
| `frontend/src/components/ChatApp.jsx` | Main chat UI: sidebar history, upload, SSE streaming, mobile hamburger |
| `frontend/src/components/AuthPage.jsx` | Login / register / Google OAuth / forgot + reset password modals |
| `frontend/src/components/Message.jsx` | Message bubbles, citation chips, confidence badge, markdown body |
| `frontend/src/App.jsx` | Root: auth state machine, OAuth callback URL parsing, toast management |

Design: dark theme (`#212121` bg, `#10a37f` accent), Outfit font, responsive off-canvas sidebar on mobile (`≤768px`).

---

## Key Design Decisions

| Decision | Rationale |
|---|---|
| PostgreSQL as unified backend | One `DATABASE_URL` covers auth, vectors, blocklist, resets. No extra infra on Railway. |
| Hybrid search (vector + FTS) via RRF | Recovers exact-match terms (IDs, names, codes) that score low on embeddings alone |
| Per-session `asyncio.Lock` in MemoryManager | Makes update→compress→replace atomic; prevents history corruption under concurrent turns |
| `asyncio.Lock` in rate limiter | Eliminates TOCTOU race when multiple coroutines check the same bucket simultaneously |
| `datetime.now(timezone.utc)` everywhere | Avoids `TypeError` with asyncpg `TIMESTAMPTZ`; naive `utcnow()` was a runtime bug |
| Session ownership via `user_id` | Prevents cross-user session access; error is identical to not-found (no info leak) |
| Orphan cleanup on upload error | If `DocumentRegistry.register()` fails after file save, the file is removed immediately |
| Shared `app.state.embedder` | All callers (pipeline, debug endpoint) reuse the same cached embedder instance |
| JWT blocklist on logout | Stateless JWTs can't be invalidated; blocklist closes the logout gap within token TTL |

---

## Scalability Path

| Scale | Vector Store | Auth/Sessions | Deployment |
|---|---|---|---|
| Dev | PGVectorStore (Docker Compose) | PostgreSQL + JSON files | Single compose stack |
| Small prod | PGVectorStore (Railway PostgreSQL) | PostgreSQL + JSON files | Railway single service |
| Large prod | Pinecone / Weaviate | PostgreSQL (managed) + Redis sessions | Kubernetes |
