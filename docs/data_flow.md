# Data Flow — RAG PDF Q&A System

This document traces the complete data path through the system for both primary operations: **PDF ingestion** and **question answering**.

---

## Flow 1: PDF Ingestion

```
User uploads PDF
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│ POST /api/v1/documents/upload                                   │
│ Content-Type: multipart/form-data                               │
│ Body: file=<PDF bytes>, session_id=<optional UUID>              │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 1: FILE VALIDATION & STORAGE                               │
│                                                                 │
│ Input:  UploadFile (bytes + filename)                           │
│ Checks: MIME type == application/pdf                            │
│         File size <= 50MB                                       │
│         Non-empty                                               │
│ Action: Generate document_id (UUID)                             │
│         Save to uploads/{document_id}_{filename}                │
│ Output: file_path, document_id                                  │
│ Errors: 400 Bad Request (invalid file)                          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 2: PDF PARSING                                             │
│                                                                 │
│ Input:  file_path                                               │
│ Engine: PyMuPDF (primary), pdfplumber (fallback)                │
│ Output: ParsedDocument                                          │
│         ├── pages: [{page_number: 1, raw_text: "...", ...}, ...]│
│         ├── metadata: {title, author, creation_date, producer}  │
│         └── page_count: int                                     │
│ Errors: 422 (corrupted/encrypted PDF)                           │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 3: TEXT CLEANING                                            │
│                                                                 │
│ Input:  raw text per page                                       │
│ Operations (in order):                                          │
│   1. Unicode NFKC normalization                                 │
│   2. Whitespace normalization                                   │
│   3. Hyphenated line-break rejoining                            │
│   4. Header/footer removal (cross-page detection)               │
│   5. Control character removal                                  │
│   6. Empty line consolidation                                   │
│ Output: cleaned full-document text + page boundary offsets      │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 4: CHUNKING                                                │
│                                                                 │
│ Input:  cleaned text, page boundaries, document_id              │
│ Strategy: Recursive character split                             │
│   Size:    512 tokens                                           │
│   Overlap: 64 tokens                                            │
│   Splits:  \n\n → \n → ". " → " "                              │
│ Output: list[Chunk]                                             │
│   Each chunk:                                                   │
│     ├── chunk_id: UUID                                          │
│     ├── document_id: UUID                                       │
│     ├── document_name: str                                      │
│     ├── chunk_index: int (0, 1, 2, ...)                         │
│     ├── text: str                                               │
│     ├── token_count: int                                        │
│     ├── page_numbers: [int, ...]                                │
│     ├── start_char_offset: int                                  │
│     └── end_char_offset: int                                    │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 5: EMBEDDING                                               │
│                                                                 │
│ Input:  list[Chunk] (text field)                                │
│ Model:  text-embedding-3-small (1536 dimensions)                │
│ Method: Batch API calls (100 chunks/batch, async)               │
│ Output: list[Chunk] with embedding field populated              │
│   Each embedding: list[float] of length 1536                    │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 6: VECTOR STORAGE                                          │
│                                                                 │
│ Input:  list[Chunk] with embeddings                             │
│ Store:  FAISS IndexFlatIP or ChromaDB collection                │
│ Stored per vector:                                              │
│   Vector:   1536-dim float32 array                              │
│   Metadata: {chunk_id, document_id, document_name,              │
│              chunk_index, page_numbers, token_count, text}       │
│ Output: Vectors indexed and searchable                          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 7: STATUS UPDATE                                           │
│                                                                 │
│ Document status: "processing" → "ready"                         │
│ If session_id provided: associate document with session          │
│ Return: 202 Accepted + DocumentUploadResponse                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Flow 2: Question Answering

```
User asks a question
       │
       ▼
┌─────────────────────────────────────────────────────────────────┐
│ POST /api/v1/query                                              │
│ Body: {question, session_id, document_ids?, top_k?}             │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 1: SESSION RESOLUTION                                      │
│                                                                 │
│ Input:  session_id                                              │
│ Action: Load session from SessionStore                          │
│ Output: Session (document_ids, conversation_history)            │
│ Errors: 404 (session not found or expired)                      │
│ Latency: <1ms (in-memory lookup)                                │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 2: QUERY REFORMULATION (conditional)                       │
│                                                                 │
│ Condition: conversation_history is non-empty                    │
│ Input:  raw question + conversation history                     │
│ Model:  gpt-4o-mini (fast, cheap)                               │
│ Action: LLM resolves pronouns/references into standalone query  │
│ Example:                                                        │
│   History: "What was Q3 revenue?"                               │
│   Follow-up: "How does it compare to Q2?"                       │
│   Standalone: "How does Q3 revenue compare to Q2 revenue?"      │
│ Output: standalone_query                                        │
│ Latency: 0ms (first turn) or 200-400ms (follow-up)             │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 3: QUERY EMBEDDING                                         │
│                                                                 │
│ Input:  standalone_query (text)                                 │
│ Model:  text-embedding-3-small                                  │
│ Output: query_embedding (1536-dim vector)                       │
│ Latency: ~100-150ms                                             │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 4: RETRIEVAL (3-stage)                                     │
│                                                                 │
│ Stage A — Vector Search:                                        │
│   Input: query_embedding, document_ids                          │
│   Action: cosine similarity search, top_k×2 candidates          │
│   Latency: 10-50ms (FAISS) / 50-100ms (ChromaDB)               │
│                                                                 │
│ Stage B — Threshold Filter:                                     │
│   Discard chunks with similarity < 0.70                         │
│                                                                 │
│ Stage C — MMR Re-ranking:                                       │
│   Select final top_k with diversity (λ=0.7)                     │
│                                                                 │
│ Output: RetrievedContext                                        │
│   ├── chunks: [{chunk, score, rank}, ...]                       │
│   └── metadata: {time_ms, candidates, scores}                   │
│ Latency: ~50-150ms total                                        │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 5: ANSWER GENERATION                                       │
│                                                                 │
│ Input:  standalone_query + retrieved chunks + history            │
│ Prompt Construction:                                            │
│   System: "Answer from context only. Cite with [Source N]."     │
│   Context: Numbered chunks with source metadata                 │
│   History: Prior Q&A turns                                      │
│   Question: The standalone query                                │
│ Model:  gpt-4o (temperature=0.1)                                │
│ Output: answer text with [Source N] references                  │
│ Latency: 500-1500ms (full) / 300-500ms to first token           │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 6: CITATION EXTRACTION                                     │
│                                                                 │
│ Input:  raw answer text + chunk metadata                        │
│ Action: Parse [Source N] references                             │
│         Map to chunk metadata (doc_name, pages, excerpt)        │
│         Validate citations against provided context             │
│ Output: list[Citation]                                          │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ Step 7: SESSION UPDATE                                          │
│                                                                 │
│ Append ConversationTurn to session history:                     │
│   {user_query, standalone_query, response, chunk_ids, timestamp}│
│ Update last_active_at                                           │
│ Enforce MAX_CONVERSATION_TURNS (drop oldest if exceeded)        │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│ RESPONSE                                                        │
│                                                                 │
│ {                                                               │
│   "answer": "Based on the report, Q3 revenue was $4.2M [1]...",│
│   "citations": [                                                │
│     {"document_name": "report.pdf", "page_numbers": [5], ...}  │
│   ],                                                            │
│   "confidence": 0.87,                                           │
│   "retrieval_metadata": {"retrieval_time_ms": 87, ...}          │
│ }                                                               │
└─────────────────────────────────────────────────────────────────┘
```

---

## Flow 3: Streaming Response (SSE Variant)

Steps 1-4 are identical to Flow 2 (all blocking, pre-stream).

At Step 5, instead of waiting for complete generation:

```
┌─────────────────────────────────────────────────────────────────┐
│ Step 5 (Streaming): SSE TOKEN DELIVERY                          │
│                                                                 │
│ Response Headers:                                               │
│   Content-Type: text/event-stream                               │
│   Cache-Control: no-cache                                       │
│                                                                 │
│ Events emitted:                                                 │
│                                                                 │
│   event: token                                                  │
│   data: {"text": "Based", "query_id": "abc-123"}                │
│                                                                 │
│   event: token                                                  │
│   data: {"text": " on", "query_id": "abc-123"}                  │
│   ...                                                           │
│                                                                 │
│   event: citation                                               │
│   data: {"citations": [...], "query_id": "abc-123"}             │
│                                                                 │
│   event: done                                                   │
│   data: {"query_id": "abc-123", "total_tokens": 142}            │
│                                                                 │
│ Time to first token: ~650-1200ms                                │
│ Total stream duration: depends on answer length                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Data Model Summary

| Entity | Key Fields | Storage |
|---|---|---|
| Document | document_id, filename, status, page_count | In-memory registry |
| Chunk | chunk_id, document_id, text, embedding, page_numbers | Vector DB |
| Session | session_id, document_ids, conversation_history | In-memory store |
| ConversationTurn | user_query, standalone_query, response, citations | Within Session |

---

## Latency Budget (Query Path)

| Stage | Typical | Worst Case | Notes |
|---|---|---|---|
| Session lookup | <1ms | <1ms | In-memory dict |
| Query reformulation | 0-400ms | 600ms | Skipped on first turn |
| Query embedding | 100-150ms | 300ms | Single OpenAI API call |
| Vector search | 10-50ms | 100ms | FAISS in-memory |
| Score filtering + MMR | 5-20ms | 50ms | CPU only |
| LLM first token | 300-500ms | 800ms | OpenAI streaming |
| **Total to first token** | **~650-1200ms** | **~1850ms** | **Under 2s target** |
