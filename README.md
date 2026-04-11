# DocMind

> **Production-grade Retrieval-Augmented Generation built from first principles — no LangChain, no LlamaIndex. Raw OpenAI SDK, explicit token budgets, hybrid search, and a fault-tolerant ingestion pipeline that handles the dirty PDFs real enterprise data throws at you.**

Every answer is grounded exclusively in your uploaded PDFs. The system is architecturally incapable of hallucinating from the LLM's prior knowledge.

---

## Live Demo

### **[docmind.up.railway.app](https://docmind.up.railway.app)**

*(Upload a PDF → ask it anything → get cited, streamed answers in real time)*

---

## Why I Built This Without a Framework

Most RAG tutorials reach for LangChain or LlamaIndex and inherit their abstractions, their latency, and their hidden costs. DocMind deliberately uses the raw **OpenAI Python SDK** throughout. Every prompt template, every token count, every cache key is explicit and instrumented. That choice pays off in three ways:

- **Latency control** — no framework middleware between the code and the API call
- **Cost visibility** — every embedding and completion is metered at the call site
- **Debuggability** — when retrieval goes wrong, the full trace is in this code, not buried in a library

---

## Engineering Decisions

### 1. PostgreSQL as the unified backend
User accounts, chunk vectors, JWT blocklist, and password reset tokens all live in one PostgreSQL instance via `asyncpg`. No separate vector database, no Redis, no SQLite sidecar. One `DATABASE_URL` covers everything — a critical simplification for Railway or any single-host deployment.

### 2. Hybrid search: vector + keyword merged via RRF
Pure embedding search struggles with exact-match terms — serial numbers, named entities, model codes. PostgreSQL's built-in full-text search (`tsvector` + `ts_rank_cd`) handles those precisely. Both ranked lists are fused using **Reciprocal Rank Fusion** (k=60), a parameter-free method that consistently outperforms weighted linear combination. The `GENERATED ALWAYS AS tsvector` column means the FTS index is maintained automatically on every insert.

### 3. Why FastAPI + SSE over WebSockets?
SSE is strictly unidirectional — the server pushes tokens, the client reads them. A RAG Q&A session fits this model exactly: one HTTP request, one streamed answer. WebSockets add bidirectional complexity (connection state, ping/pong, reconnection logic) with zero benefit here. FastAPI's async generator support makes SSE a native first-class pattern.

### 4. Why query reformulation on every turn?
A question like *"What does it say about risk?"* is semantically ambiguous — embedding "it" and "risk" without document context retrieves the wrong chunks. `QueryReformulator` sends every query (plus conversation history) through the LLM before embedding, resolving coreferences and expanding inferential language into explicit search terms. The added ~80–350ms pays for itself in retrieval precision on every non-trivial question.

### 5. Why MMR instead of pure top-k?
Fetching the top-20 nearest vectors and naively passing them to the LLM floods the context window with near-duplicate chunks — the same paragraph from overlapping chunk windows. **Maximal Marginal Relevance** scores each candidate as `λ·similarity − (1−λ)·max_similarity_to_selected`, enforcing diversity. The LLM sees 10 genuinely distinct pieces of evidence instead of 10 paraphrases of the same sentence.

### 6. Three-layer cost control

| Layer | Mechanism | Saves |
|---|---|---|
| **EmbeddingCache** | LRU, keyed on query text, 24h TTL | Eliminates repeat embedding API calls |
| **ResponseCache** | Keyed on `hash(query + session + docs + turn_count)`, 60s TTL | Short-circuits double-submissions instantly |
| **Memory Token Budget** | `ContextBuilder` hard-caps history at 1024 tokens; `MemoryCompressor` summarises old turns via the LLM when turn count exceeds threshold | Prevents unbounded context growth |

### 7. Fault-tolerant ingestion: 3-level PDF fallback

```
Level 1: PyMuPDF (fitz)
  ├── Fast; handles text layers, form fields, annotations
  └── Quality check: avg < 50 chars/page or > 60% short lines? → fallback

Level 2: pdfplumber
  ├── Better for multi-column and tabular layouts
  └── Word-by-word reconstruction if page.extract_text() returns nothing

Level 3: Tesseract OCR (pdf2image + pytesseract)
  ├── Last resort for scanned/image-only PDFs
  └── 200 DPI rasterization; explicit error if OCR tools not installed
```

### 8. Async safety
- Rate limiter bucket operations wrapped in `asyncio.Lock` per user — eliminates the TOCTOU race under concurrent requests
- `MemoryManager` update→compress→replace wrapped in per-session `asyncio.Lock` — prevents history corruption when two turns complete simultaneously
- All datetime comparisons use `datetime.now(timezone.utc)` (not `utcnow()`) to avoid `TypeError` with asyncpg's `TIMESTAMPTZ` columns

---

## Features

- **React + Vite frontend** — dark ChatGPT-style UI, responsive off-canvas sidebar, real-time SSE streaming, persistent session history
- **Full auth system** — email/password registration + login, Google OAuth, forgot/reset password, JWT logout with server-side blocklist
- **Hybrid retrieval** — pgvector cosine similarity + PostgreSQL FTS merged via RRF
- **Conversational memory** — multi-turn follow-up questions resolved via query reformulation + history compression
- **Inference query support** — vague questions like *"Is he a bad guy?"* expanded into semantic search terms before retrieval
- **Source citations** — every answer cites the exact PDF page and excerpt used
- **Session ownership enforcement** — sessions are user-scoped; cross-user access returns the same error as not-found
- **3-level PDF ingestion** — PyMuPDF → pdfplumber → Tesseract OCR for scanned/image-only PDFs
- **MMR retrieval** — prevents context redundancy in the LLM prompt
- **Optional reranking** — cross-encoder or Cohere reranker for higher precision
- **Three-layer cost control** — embedding cache + response cache + memory token budget
- **No framework bloat** — raw OpenAI SDK; every prompt and token budget is explicit

---

## Architecture

```
React + Vite SPA  (dark theme, responsive, SSE streaming)
         │
         ▼
Auth Layer  (JWT HS256, 1yr TTL)
  POST /auth/register    POST /auth/login
  GET  /auth/google      GET  /auth/google/callback
  POST /auth/forgot-password  POST /auth/reset-password
  GET  /auth/me          POST /auth/logout
  UserStore (PostgreSQL) · TokenBlocklist (PostgreSQL)
  PasswordResetStore (PostgreSQL)
         │
         ▼
API Layer  (all routes below require Authorization: Bearer)
  │
  ├── POST /documents/upload  ──►  IngestionPipeline (BackgroundTask)
  │                                   parse → clean → chunk → embed
  │                                   → PGVectorStore (pgvector + FTS)
  │                                   orphan cleanup on error
  │
  └── POST /query / /query/stream  ──►  RAGPipeline  ◄── single orchestrator
                                          │
                                          ├── ResponseCache (check/store)
                                          ├── QueryReformulator (always runs)
                                          ├── EmbeddingCache
                                          ├── RetrieverService
                                          │     pgvector cosine search
                                          │     + PostgreSQL FTS search
                                          │     → RRF merge → threshold filter
                                          ├── RerankerService (optional)
                                          ├── MMR selection
                                          ├── MemoryManager (read history)
                                          ├── RAGChain (prompt + LLM + citations)
                                          └── MemoryManager (write turn, per-session lock)
```

### Layer Responsibilities

| Layer | Location | Purpose |
|---|---|---|
| **Auth** | `app/api/v1/auth.py` | JWT, bcrypt, Google OAuth, forgot/reset password, logout blocklist |
| **Pipeline** | `app/pipeline/` | End-to-end orchestration — the only layer API handlers call |
| **Chains** | `app/chains/` | LLM-only: prompt assembly, OpenAI call, citation extraction |
| **Services** | `app/services/` | Single-responsibility units: parse, chunk, embed, retrieve, rerank, stream |
| **Cache** | `app/cache/` | Embedding cache (24h) and response cache (60s) |
| **Memory** | `app/memory/` | History formatting, token budgeting, compression; per-session async lock |
| **DB** | `app/db/` | PGVectorStore (pgvector + FTS), SessionStore, DocumentRegistry, UserStore, TokenBlocklist |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Web framework | FastAPI (async) |
| LLM + Embeddings | OpenAI (`gpt-4o`, `text-embedding-3-small`) — raw SDK, no wrappers |
| Vector store | PostgreSQL + pgvector (cosine) + PostgreSQL FTS → RRF hybrid |
| PDF parsing | PyMuPDF → pdfplumber → Tesseract OCR (3-level fallback) |
| Authentication | python-jose (JWT) + bcrypt + asyncpg (PostgreSQL) |
| Tokenisation | tiktoken |
| Reranker (optional) | Cohere Rerank API or local cross-encoder |
| Frontend | React 18 + Vite 5 (served as static files from `app/frontend/`) |
| Containerisation | Docker + Docker Compose |
| Deployment | Railway |

---

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/garg-kavya/DocMind
cd DocMind
cp .env.example .env
# Edit .env — set OPENAI_API_KEY and DATABASE_URL at minimum
```

### 2. Run with Docker Compose

```bash
docker compose up --build
```

This starts PostgreSQL and the app together. Open **`http://localhost:8000`**.

### 3. Run locally (without Docker)

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Requires a running PostgreSQL instance. Set `DATABASE_URL` in `.env`.

API docs: `http://localhost:8000/docs`

---

## Deployment (Railway)

1. Push this repo to GitHub
2. Create a new Railway project → "Deploy from GitHub repo"
3. Add a PostgreSQL plugin — Railway injects `DATABASE_URL` automatically
4. Add `OPENAI_API_KEY` in Railway's environment variables
5. Optionally add `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` for Google OAuth
6. Railway auto-detects `Dockerfile` and `railway.json`; deploys on every push

---

## API

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| `POST` | `/api/v1/auth/register` | No | Register; returns JWT + user info |
| `POST` | `/api/v1/auth/login` | No | Login; returns JWT + user info |
| `GET` | `/api/v1/auth/google` | No | Redirect to Google OAuth (501 if unconfigured) |
| `GET` | `/api/v1/auth/google/callback` | No | OAuth callback; redirects to frontend with token |
| `POST` | `/api/v1/auth/forgot-password` | No | Send password reset link (always 200) |
| `POST` | `/api/v1/auth/reset-password` | No | Set new password; returns JWT |
| `GET` | `/api/v1/auth/me` | Yes | Current user info |
| `POST` | `/api/v1/auth/logout` | Yes | Blocklist current token (204) |
| `POST` | `/api/v1/documents/upload` | Yes | Upload and ingest a PDF (202, async) |
| `GET` | `/api/v1/documents/{id}` | Yes | Document processing status |
| `GET` | `/api/v1/documents` | Yes | List all documents |
| `DELETE` | `/api/v1/documents/{id}` | Yes | Remove document and its vectors |
| `POST` | `/api/v1/sessions` | Yes | Create a conversation session |
| `GET` | `/api/v1/sessions/{id}` | Yes | Session details + conversation history |
| `DELETE` | `/api/v1/sessions/{id}` | Yes | Delete session |
| `POST` | `/api/v1/query` | Yes | Ask a question (full response) |
| `POST` | `/api/v1/query/stream` | Yes | Ask a question (SSE streaming) |
| `GET` | `/api/v1/health` | No | Service health + stats |
| `GET` | `/api/v1/debug/index` | Yes | Vector index stats + registry doc list |
| `GET` | `/api/v1/debug/search?q=...` | Yes | Raw similarity scores for a query |

Full contracts: [`docs/api_contracts.md`](docs/api_contracts.md)

---

## Usage Example

```bash
# 1. Register
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com", "password": "secret123"}'
# → {"access_token": "eyJ...", "user_id": "...", "email": "...", "name": null}

TOKEN="eyJ..."

# 2. Upload a PDF
curl -X POST http://localhost:8000/api/v1/documents/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@report.pdf"
# → {"document_id": "a1b2...", "status": "processing"}

# 3. Poll until ready
curl http://localhost:8000/api/v1/documents/a1b2... \
  -H "Authorization: Bearer $TOKEN"
# → {"status": "ready", "total_chunks": 92}

# 4. Create a session
SESSION=$(curl -s -X POST http://localhost:8000/api/v1/sessions \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"document_ids": ["a1b2..."]}' | jq -r .session_id)

# 5. Ask a question
curl -X POST http://localhost:8000/api/v1/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"question\": \"What were the key risks?\", \"session_id\": \"$SESSION\"}"
```

```json
{
  "answer": "Three key risks were identified: supply chain disruptions [Source 1], regulatory costs [Source 2], and cybersecurity threats [Source 3].",
  "citations": [
    {"document_name": "report.pdf", "page_numbers": [32], "chunk_index": 67,
     "excerpt": "Supply chain disruptions remain a primary concern..."}
  ],
  "query_id": "q-abc-123",
  "confidence": 0.87,
  "retrieval_metadata": {
    "retrieval_time_ms": 64,
    "hybrid_search_applied": true,
    "reranker_applied": false
  }
}
```

---

## Configuration

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | *(required)* | OpenAI API key |
| `DATABASE_URL` | *(required)* | PostgreSQL connection string |
| `LLM_MODEL` | `gpt-4o` | Generation model |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | Embedding model (1536 dims) |
| `CHUNK_SIZE_TOKENS` | `512` | Tokens per chunk |
| `CHUNK_OVERLAP_TOKENS` | `64` | Overlap between adjacent chunks |
| `TOP_K` | `10` | Final chunks passed to LLM |
| `TOP_K_CANDIDATES` | `20` | Candidates fetched before reranking/MMR |
| `SIMILARITY_THRESHOLD` | `0.0` | Min relevance score (0.0 = disabled) |
| `RERANKER_BACKEND` | `none` | `none`, `cross_encoder`, or `cohere` |
| `COHERE_API_KEY` | — | Required if `RERANKER_BACKEND=cohere` |
| `JWT_SECRET_KEY` | *(change in prod)* | HS256 signing secret (min 32 chars in production) |
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `525600` | Token TTL (default: 1 year) |
| `GOOGLE_CLIENT_ID` | — | Google OAuth client ID (optional) |
| `GOOGLE_CLIENT_SECRET` | — | Google OAuth client secret (optional) |
| `SMTP_HOST` / `SMTP_PORT` | — | SMTP config for password reset emails (optional) |
| `SMTP_USER` / `SMTP_PASSWORD` | — | SMTP credentials |
| `EMBEDDING_CACHE_TTL_SECONDS` | `86400` | 24h embedding cache TTL |
| `RESPONSE_CACHE_TTL_SECONDS` | `60` | 60s response cache TTL |
| `MEMORY_TOKEN_BUDGET` | `1024` | Max tokens for conversation history |
| `MAX_UPLOAD_SIZE_MB` | `50` | Maximum PDF upload size |
| `ENVIRONMENT` | `development` | Set to `production` to enforce JWT secret strength |

> **`SIMILARITY_THRESHOLD` note:** With `text-embedding-3-small`, cosine similarity for semantically related (but not near-identical) text typically falls in the 0.10–0.29 range. The default `0.0` disables filtering. Raise only if you see irrelevant chunks in answers.

Full reference: [`.env.example`](.env.example)

---

## Performance

| Metric | Value | How |
|---|---|---|
| Time to first token | ~600–1100ms | Pre-computed embeddings + SSE streaming |
| Median query latency | <1.5s | pgvector + embedding cache + streaming |
| Precision@10 (hybrid, no reranker) | ~0.65–0.75 | 512-token chunks + RRF + MMR |
| Precision@10 (hybrid + cross-encoder) | ~0.72–0.84 | + cross-encoder reranking |
| Precision@10 (hybrid + Cohere) | ~0.76–0.88 | + Cohere Rerank |

Latency breakdown (hybrid, no reranker):

```
JWT verify + blocklist    <2ms
Session lookup            <1ms
Response cache check      <1ms
Reformulation          80–350ms  (every turn)
Embedding               1–150ms  (near-zero on cache hit)
pgvector cosine          5–40ms
PostgreSQL FTS           3–20ms
RRF merge                  <1ms
MMR selection            5–20ms
LLM first token       300–600ms  (streaming)
─────────────────────────────────
Total to first token  ~600–1100ms
```

---

## Tests

```bash
pytest                               # all tests
pytest tests/test_rag_pipeline.py    # pipeline integration
pytest -m "not integration"          # skip tests requiring OpenAI
pytest --cov=app                     # with coverage
```

---

## Documentation

| Document | Description |
|---|---|
| [`docs/architecture.md`](docs/architecture.md) | Full layer model, component reference, design decisions |
| [`docs/data_flow.md`](docs/data_flow.md) | Step-by-step traces: ingestion, query, auth, password reset |
| [`docs/retrieval_strategy.md`](docs/retrieval_strategy.md) | Hybrid search, RRF, chunk tuning, MMR, reranking, P@10 |
| [`docs/api_contracts.md`](docs/api_contracts.md) | Full JSON request/response for all 20 endpoints |

---

## Project Structure

```
app/
├── api/
│   ├── v1/           auth, documents, query, sessions, health, debug
│   └── middleware/   token-bucket rate limiter (asyncio.Lock), error handler
├── pipeline/
│   ├── rag_pipeline.py        query orchestrator (single entry point)
│   └── ingestion_pipeline.py  PDF ingestion orchestrator
├── chains/           prompt assembly, OpenAI call, citation extraction
├── services/
│   ├── pdf_processor          PyMuPDF → pdfplumber → Tesseract (3-level)
│   ├── text_cleaner, chunker, embedder
│   ├── retriever              hybrid vector+FTS via RRF, threshold, MMR
│   ├── reranker               cross-encoder / Cohere (optional)
│   ├── query_reformulator     coreference + inference expansion
│   └── streaming              SSE event formatting
├── cache/            EmbeddingCache (24h) + ResponseCache (60s)
├── memory/           MemoryManager (per-session lock), ContextBuilder, MemoryCompressor
├── db/
│   ├── pgvector_store.py      cosine search + FTS keyword search
│   ├── faiss_store.py         optional in-process store
│   ├── session_store.py       JSON-backed, user_id ownership
│   ├── document_registry.py   JSON-backed status + metadata
│   ├── user_store.py          PostgreSQL, email + Google OAuth
│   ├── token_blocklist.py     PostgreSQL JWT blocklist
│   └── password_reset_store.py PostgreSQL one-time tokens
├── models/           QueryContext, ScoredChunk, GeneratedAnswer, Session, User…
├── schemas/          Pydantic API + metadata schemas
├── utils/            file_utils, token_counter, logging
├── exceptions.py     Centralised exception hierarchy
├── config.py         All settings + JWT secret validator
├── dependencies.py   DI wiring, app state (embedder, vector_store, …)
└── main.py           FastAPI app + lifespan startup

frontend/             React + Vite source
│   ├── src/
│   │   ├── api.js             apiFetch wrapper (auth, error normalisation)
│   │   ├── store.js           localStorage: sessions + auth
│   │   ├── components/
│   │   │   ├── App.jsx        root: auth state, OAuth callback, toasts
│   │   │   ├── ChatApp.jsx    sidebar, upload, streaming chat, hamburger
│   │   │   ├── AuthPage.jsx   login/register/Google/forgot/reset
│   │   │   └── Message.jsx    bubbles, citations, confidence, markdown
│   │   └── index.css          dark design system (Outfit font, #10a37f accent)
│   ├── index.html             SVG favicon, Google Fonts
│   └── vite.config.js         output → app/frontend/, dev proxy → :8000

app/frontend/         Built output (served by FastAPI StaticFiles)
data/                 sessions.json, registry.json, uploads/
tests/                Unit + integration stubs
docs/                 Architecture, data flow, retrieval strategy, API contracts
Dockerfile            Multi-stage build (tesseract-ocr + poppler-utils included)
docker-compose.yml    PostgreSQL + app, named volumes
railway.json          Railway deployment config
requirements.txt      Pinned production dependencies
```

---

## License

MIT
