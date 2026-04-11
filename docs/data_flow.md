# Data Flow — DocMind

---

## Flow 1: PDF Ingestion

```
Client: POST /api/v1/documents/upload  (multipart/form-data)
        Authorization: Bearer <JWT>
              │
              ▼
┌────────────────────────────────────────────────────────────────────┐
│ API Handler (documents.py)                                         │
│ 0. get_current_user() — verify JWT, check TokenBlocklist           │
│ 1. Validate MIME type: must contain "pdf"; raise InvalidFileType   │
│ 2. Validate size ≤ MAX_UPLOAD_SIZE_MB                              │
│ 3. FileUtils.save_upload() → (file_path, document_id)             │
│ 4. DocumentRegistry.register(document_id, ...) → status=uploaded  │
│    On RegistryError: os.unlink(file_path) — orphan cleanup         │
│ 5. Launch IngestionPipeline.run() as BackgroundTask                │
│ 6. Return 202 Accepted immediately                                 │
└──────────────────────────────┬─────────────────────────────────────┘
                               │ (background)
                               ▼
┌────────────────────────────────────────────────────────────────────┐
│ IngestionPipeline.run()                                            │
│                                                                    │
│ Step 1: DocumentRegistry.update_status(→ "processing")            │
│                                                                    │
│ Step 2: PDFProcessorService.parse(file_path, document_id)         │
│   ├── PyMuPDF  (primary)   sort=True for correct reading order     │
│   │   also extracts annotation text and form widget fields         │
│   ├── pdfplumber (fallback) if chars_per_page < threshold          │
│   │   or garbled-text detected (>60% very-short lines)             │
│   └── Tesseract OCR via pdf2image (last resort, DPI=200)           │
│   → ParsedDocument {pages, pdf_metadata, parser_used}             │
│   On PDFParsingError → status="error"                              │
│                                                                    │
│ Step 3: TextCleanerService.clean(parsed_document)                  │
│   Normalises: whitespace, ligatures, mojibake, soft hyphens,       │
│   control chars, line noise                                        │
│                                                                    │
│ Step 4: ChunkerService.chunk(cleaned_text, ..., document_id)       │
│   Recursive split: 512 tokens, 64-token overlap                    │
│   Boundary hierarchy: \n\n → \n → ". " → " "                      │
│   Each Chunk: {chunk_id, chunk_index, page_numbers,                │
│                token_count, text, start/end_char_offset}           │
│   Zero-chunk guard: 0 chunks → status="error"                     │
│                                                                    │
│ Step 5: EmbedderService.embed_chunks(chunks)                       │
│   Batch OpenAI calls (100 chunks/batch)                            │
│   Model: text-embedding-3-small → 1536-dim float32 vectors         │
│   On EmbeddingAPIError → status="error"                            │
│                                                                    │
│ Step 6: VectorStore.add_chunks(chunks)   [PGVectorStore]           │
│   INSERT INTO document_chunks (chunk_id, document_id,              │
│     document_name, chunk_index, text, token_count,                 │
│     page_numbers, start_char_offset, end_char_offset, embedding)   │
│   FTS column text_search is GENERATED ALWAYS AS                    │
│     to_tsvector('simple', text) STORED — auto-updated              │
│   On StorageWriteError → status="error"                            │
│                                                                    │
│ Step 7: DocumentRegistry.update_status(→ "ready")                  │
│         DocumentRegistry.set_ingestion_metadata(chunks, pages, …)  │
└────────────────────────────────────────────────────────────────────┘
```

---

## Flow 2: Query — Non-Streaming

```
Client: POST /api/v1/query
        Authorization: Bearer <JWT>
        {"question": "…", "session_id": "…", "document_ids": […], "top_k": 10}
              │
              ▼
┌────────────────────────────────────────────────────────────────────┐
│ API Handler (query.py)                                             │
│ 0. get_current_user() — verify JWT, check TokenBlocklist           │
│ 1. Validate QueryRequest (Pydantic)                                │
│ 2. RAGPipeline.run(question, session_id, document_ids, top_k)      │
│ 3. Map GeneratedAnswer → QueryResponse                             │
│ 4. Return 200 OK                                                   │
└──────────────────────────────┬─────────────────────────────────────┘
                               │
                               ▼
┌────────────────────────────────────────────────────────────────────┐
│ RAGPipeline.run()                                                  │
│                                                                    │
│ Step 1: SessionStore.get_session(session_id)                       │
│   Checks session.user_id == current_user.user_id                   │
│   → SessionNotFoundError if missing or unauthorised (→ 404)        │
│   → NoDocumentsError if doc list empty (→ 409)                     │
│                                                                    │
│ Step 2: ResponseCache.get_or_generate(                             │
│           query, session_id, document_ids, turn_count,             │
│           generate_fn=<steps 3–11>)                                │
│   HIT  → return cached GeneratedAnswer (cache_hit=True)            │
│   MISS → continue ↓                                                │
│                                                                    │
│ Step 3: Query Reformulation (always runs)                          │
│   QueryReformulator.reformulate(raw_query, history)                │
│   a) Coreference resolution:                                       │
│      "What about their revenue?"                                   │
│      → "What was Acme Corp's Q3 2024 revenue?"                    │
│   b) Inference/vague query expansion:                              │
│      "Is he a bad guy?"                                            │
│      → "professional misconduct unethical behaviour                │
│          criminal record character flaws"                          │
│   Output: standalone_query                                         │
│                                                                    │
│ Step 4: EmbeddingCache.get_or_embed(standalone_query)              │
│   HIT  → cached 1536-dim vector  (~0–1ms)                         │
│   MISS → EmbedderService.embed_query() → cache  (~150ms)          │
│                                                                    │
│ Step 5: Hybrid Retrieval  (RetrieverService.retrieve)              │
│                                                                    │
│   5a. VectorStore.search(query_embedding, TOP_K_CANDIDATES=20)     │
│       pgvector cosine similarity: 1 - (embedding <=> $query)       │
│       Scoped to session document_ids via WHERE clause              │
│       → list[ScoredChunk] sorted by cosine score desc             │
│                                                                    │
│   5b. VectorStore.keyword_search(standalone_query, top_k=20)      │
│       PostgreSQL FTS: plainto_tsquery('simple', …)                 │
│       Scored via ts_rank_cd, normalised to [0, 1]                  │
│       → list[ScoredChunk] sorted by FTS score desc                │
│                                                                    │
│   5c. RRF merge:  for each list ranked by position                 │
│       rrf_score(chunk) += 1 / (60 + rank + 1)                     │
│       Merge both lists → sort by rrf_score desc                   │
│       → deduplicated list[ScoredChunk] with rrf similarity_score  │
│                                                                    │
│   5d. Threshold filter: discard score < SIMILARITY_THRESHOLD       │
│       (default 0.0 = disabled)                                     │
│       Output: list[ScoredChunk] (bi_encoder_score set)             │
│                                                                    │
│ Step 6: Reranking (conditional)                                    │
│   IF RerankerService.is_enabled():                                 │
│     Cross-encoder or Cohere reranker scores query ↔ chunk jointly  │
│     similarity_score ← reranker score                              │
│     bi_encoder_score preserved for diagnostics                     │
│   On RerankerError → log warning, fall back to bi-encoder order    │
│                                                                    │
│ Step 7: MMR Selection  (RetrieverService.apply_mmr, top_k=10)      │
│   score(i) = λ·similarity(i, query)                                │
│            − (1−λ)·max_over_selected(diversity_penalty(i, j))      │
│   Same-doc penalty: 1 / (1 + |chunk_index_i − chunk_index_j|)     │
│   Cross-doc penalty: 0 (maximally diverse)                         │
│   λ = MMR_DIVERSITY_FACTOR = 0.7                                   │
│   Skipped if candidates ≤ top_k (no diversity gain possible)       │
│   → final top-10 list[ScoredChunk] with rank set (1-based)         │
│                                                                    │
│ Step 8: MemoryManager.get_formatted_history(                       │
│           session_id, token_budget=1024)                           │
│   ContextBuilder serialises turns ≤ 1024 tokens                    │
│   Trims oldest turns first if over budget                          │
│   → formatted_history string                                       │
│                                                                    │
│ Step 9: QueryContext assembled:                                     │
│   {raw_query, standalone_query, query_id (UUID),                   │
│    session_id, document_ids, query_embedding,                      │
│    formatted_history, reranker_applied, cache_hit=False}           │
│                                                                    │
│ Step 10: RAGChain.invoke(query_context, retrieved_context)         │
│   Prompt: system + context_block (top-k chunks) +                  │
│            history + question                                      │
│   OpenAI ChatCompletion: gpt-4o, temperature=0.1                   │
│   Parse [Source N] tags → Citation objects                         │
│   Confidence: normalised cosine similarity of top chunk            │
│   On GenerationAPIError → 502                                      │
│   On ContextTooLongError → trim lowest-scored chunks, retry        │
│                                                                    │
│ Step 11: MemoryManager.record_turn(session_id, …)                  │
│   async with self._session_locks[session_id]:                      │
│     SessionStore.update_session(session_id, turn)                  │
│     if should_compress: MemoryCompressor.compress() →              │
│       SessionStore.replace_history(session_id, compressed)         │
│                                                                    │
│ Return: GeneratedAnswer + PipelineMetadata (all stage timings)     │
└────────────────────────────────────────────────────────────────────┘
```

---

## Flow 3: Query — Streaming (SSE)

Steps 1, 3–9 are identical to Flow 2.

Step 2 (ResponseCache) is **skipped** — streaming responses cannot be replayed.

```
Step 10 (streaming): RAGChain.stream(query_context, retrieved_context)
  OpenAI ChatCompletion with stream=True
  Tokens yielded as they arrive → StreamingHandler wraps as SSE:

    event: token
    data: {"text": "The", "query_id": "abc-123"}

    event: token
    data: {"text": " report", "query_id": "abc-123"}

    ...

    event: citation
    data: {"citations": [{…}], "query_id": "abc-123"}

    event: done
    data: {"query_id": "abc-123", "total_tokens": 142,
           "reranker_applied": true, "confidence": 0.87}

  NOTE: X-Query-Id response header is set only when query_id is
  available at header-write time. The query_id is always present
  in the "done" event body regardless.

Step 11: MemoryManager.record_turn() — after stream is exhausted
```

---

## Flow 4: Authentication — Email/Password

```
Register:  POST /auth/register  {email, password}
  → bcrypt.hashpw(password)
  → UserStore.create_user(email, hashed_password)
  → create_access_token(user_id, email)  [HS256 JWT, 1yr TTL]
  ← TokenResponse {access_token, user_id, email, name}

Login:  POST /auth/login  {email, password}
  → UserStore.get_by_email(email)
  → bcrypt.checkpw(password, user.hashed_password)
  → create_access_token(user_id, email)
  ← TokenResponse {access_token, user_id, email, name}

Logout:  POST /auth/logout
  → decode JWT → extract jti, exp
  → TokenBlocklist.add(jti, expires_at=datetime.now(timezone.utc) + remaining_ttl)
  ← 204 No Content
  All subsequent requests with this token: TokenBlocklist lookup → 401
```

---

## Flow 5: Authentication — Google OAuth

```
GET /auth/google
  → settings.google_client_id present? No → 501
  → Redirect to accounts.google.com/o/oauth2/v2/auth?
        client_id=…&redirect_uri=…&scope=openid email profile

GET /auth/google/callback?code=…&state=…
  → httpx.AsyncClient(timeout=10.0).post(token endpoint)
  → Decode id_token → {email, name, sub (google_id)}
  → UserStore.get_by_email(email):
      Found (email/pass user) → link google_id, set auth_provider="google"
      Found (google user)     → update name if changed
      Not found               → create_user(email, name, google_id)
  → create_access_token(user_id, email)
  → Redirect to frontend /#access_token=…&user_id=…&email=…&name=…
```

---

## Flow 6: Password Reset

```
POST /auth/forgot-password  {email}
  → Always returns 200 (no enumeration)
  → UserStore.get_by_email(email) → user exists?
  → PasswordResetStore.create_token(user_id, email)
  → Send email via SMTP: link = /reset-password?token=<uuid>
  (If SMTP not configured → 200 returned, no email sent)

POST /auth/reset-password  {token, new_password}
  → PasswordResetStore.verify_and_consume(token) → user_id
  → bcrypt.hashpw(new_password)
  → UserStore.update_password(user_id, hashed)
  → create_access_token(user_id, email)
  ← TokenResponse {access_token, user_id, email, name}
```

---

## Latency Budget

| Stage | Typical | Worst Case | Notes |
|---|---|---|---|
| JWT verify + blocklist check | <2ms | <5ms | in-memory blocklist cache |
| Session lookup | <1ms | <1ms | in-memory dict |
| Response cache check | <1ms | <1ms | cache hit returns immediately |
| Query reformulation (LLM) | 80–350ms | 600ms | runs on every turn |
| Query embedding | 1–150ms | 300ms | ~0ms on cache hit |
| pgvector cosine search | 5–40ms | 80ms | indexed ANN on PostgreSQL |
| PostgreSQL FTS search | 3–20ms | 50ms | `tsvector` GIN index |
| RRF merge | <1ms | <1ms | CPU only |
| Threshold filter | <1ms | <1ms | CPU only |
| Cross-encoder reranking | 0–400ms | 600ms | 0 when disabled |
| MMR selection | 5–20ms | 50ms | CPU only |
| Memory read | <1ms | <1ms | in-memory |
| LLM first token | 300–600ms | 900ms | OpenAI streaming |
| **Total to first token** | **~600–1100ms** | **~1900ms** | **≤ 2s target** |

---

## Data Model Flow

```
Upload                               Query
  │                                     │
  ▼                                     ▼
PDFMetadata                       QueryContext {
IngestionMetadata            →        raw_query, standalone_query,
      │                               query_id, session_id,
      ▼                               document_ids, query_embedding,
ChunkMetadata                         formatted_history,
(stored in pgvector)                  reranker_applied, cache_hit
                                  }
                                     │
                                     ▼
                                RetrievedContext {
                                    chunks: list[ScoredChunk {
                                        chunk, similarity_score,
                                        bi_encoder_score,
                                        rerank_score, rank
                                    }],
                                    retrieval_metadata,
                                    hybrid_search_applied
                                }
                                     │
                                     ▼
                                GeneratedAnswer {
                                    answer_text, citations,
                                    confidence, query_id,
                                    cache_hit,
                                    retrieval_context,
                                    pipeline_metadata: PipelineMetadata
                                }
```
