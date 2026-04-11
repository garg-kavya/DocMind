# API Contracts — DocMind

All endpoints are prefixed with `/api/v1`. All request/response bodies are JSON unless specified.

Endpoints that require authentication expect:
```
Authorization: Bearer <access_token>
```
A missing, expired, or logged-out token returns `401 Unauthorized`.

Public endpoints (no auth required): `/auth/register`, `/auth/login`, `/auth/google`, `/auth/google/callback`, `/auth/forgot-password`, `/auth/reset-password`, `/health`.

---

## 0. Authentication

### `POST /api/v1/auth/register`

#### Request Body

```json
{
    "email": "user@example.com",
    "password": "mysecretpassword"
}
```

#### Response — `201 Created`

```json
{
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "user_id": "e5f6a7b8-c9d0-1234-abcd-567890123456",
    "email": "user@example.com",
    "name": null
}
```

#### Error Responses

**409 Conflict — Email already registered:**
```json
{"detail": "Email already registered."}
```

**409 Conflict — Email linked to Google account:**
```json
{"detail": "This email is linked to a Google account. Please sign in with Google."}
```

---

### `POST /api/v1/auth/login`

#### Request Body

```json
{
    "email": "user@example.com",
    "password": "mysecretpassword"
}
```

#### Response — `200 OK`

```json
{
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "user_id": "e5f6a7b8-c9d0-1234-abcd-567890123456",
    "email": "user@example.com",
    "name": "Jane Smith"
}
```

#### Error Responses

**404 Not Found — No account with this email:**
```json
{"detail": "No account found with this email. Please sign up first."}
```

**400 Bad Request — Google-linked account:**
```json
{"detail": "This account uses Google sign-in. Please click 'Sign in with Google'."}
```

**403 Forbidden — Wrong password:**
```json
{"detail": "Incorrect password. Please try again."}
```

---

### `GET /api/v1/auth/google`

Redirects the browser to Google's OAuth consent screen.

**501 Not Implemented** — returned when `GOOGLE_CLIENT_ID` is not set on the server. The frontend checks for this and hides the Google button.

---

### `GET /api/v1/auth/google/callback?code=…&state=…`

Handles the OAuth redirect from Google. On success, redirects the browser to the frontend with credentials in the URL fragment:

```
/#access_token=<jwt>&user_id=<uuid>&email=<email>&name=<name>
```

The frontend (`App.jsx`) parses the fragment, stores auth in `localStorage`, and transitions to the chat view.

---

### `POST /api/v1/auth/forgot-password`

#### Request Body

```json
{
    "email": "user@example.com"
}
```

#### Response — `200 OK` (always, regardless of whether email exists)

```json
{
    "message": "If that email is registered, a reset link has been sent."
}
```

No email is sent if SMTP is not configured. The `200` response is always returned to prevent email enumeration.

---

### `POST /api/v1/auth/reset-password`

#### Request Body

```json
{
    "token": "abc123def456...",
    "new_password": "newsecretpassword"
}
```

`token` is the one-time value from the reset link query parameter. It is consumed on use.

#### Response — `200 OK`

```json
{
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "user_id": "e5f6a7b8-c9d0-1234-abcd-567890123456",
    "email": "user@example.com",
    "name": "Jane Smith"
}
```

The user is immediately signed in after resetting their password.

#### Error Responses

**400 Bad Request — Invalid or expired token:**
```json
{"detail": "Invalid or expired reset token."}
```

---

### `GET /api/v1/auth/me`

Requires `Authorization: Bearer <token>`.

#### Response — `200 OK`

```json
{
    "user_id": "e5f6a7b8-c9d0-1234-abcd-567890123456",
    "email": "user@example.com",
    "name": "Jane Smith",
    "auth_provider": "email"
}
```

`auth_provider` is `"email"` or `"google"`.

---

### `POST /api/v1/auth/logout`

Requires `Authorization: Bearer <token>`.

Adds the token's JTI to the blocklist. The token is rejected on all subsequent requests until its original expiry.

#### Response — `204 No Content`

---

## 1. PDF Upload

### `POST /api/v1/documents/upload`

**Content-Type:** `multipart/form-data`

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | File (binary) | Yes | PDF file |
| `session_id` | string (UUID) | No | Associate with an existing session |

#### Response — `202 Accepted`

```json
{
    "document_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "filename": "annual_report_2024.pdf",
    "file_size_bytes": 2458901,
    "page_count": 47,
    "total_chunks": 0,
    "status": "processing",
    "message": "Document uploaded successfully. Processing in progress.",
    "created_at": "2026-04-12T10:30:00Z"
}
```

`total_chunks` is 0 until status becomes `"ready"`. Poll `GET /documents/{id}` for updates.

#### Error Responses

**400 — Invalid file type:**
```json
{"detail": "Only PDF files are accepted."}
```

**400 — File too large:**
```json
{"detail": "File size 67.2MB exceeds maximum allowed 50MB."}
```

---

## 2. Document Status

### `GET /api/v1/documents/{document_id}`

#### Response — `200 OK`

```json
{
    "document_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "filename": "annual_report_2024.pdf",
    "status": "ready",
    "page_count": 47,
    "total_chunks": 92,
    "metadata": {
        "title": "Acme Corp Annual Report 2024",
        "author": "Finance Department",
        "creation_date": "2024-12-15",
        "producer": "Microsoft Word"
    },
    "created_at": "2026-04-12T10:30:00Z",
    "processed_at": "2026-04-12T10:30:14Z",
    "error_message": null
}
```

| Status | Meaning |
|---|---|
| `"uploaded"` | File saved, not yet processing |
| `"processing"` | Parse → chunk → embed in progress |
| `"ready"` | Fully indexed and queryable |
| `"error"` | Processing failed; see `error_message` |

---

## 3. List Documents

### `GET /api/v1/documents`

Returns all documents belonging to the authenticated user.

#### Response — `200 OK`

```json
{
    "documents": [
        {
            "document_id": "a1b2c3d4-...",
            "filename": "annual_report_2024.pdf",
            "status": "ready",
            "page_count": 47,
            "total_chunks": 92,
            "created_at": "2026-04-12T10:30:00Z"
        }
    ],
    "total_count": 1
}
```

---

## 4. Delete Document

### `DELETE /api/v1/documents/{document_id}`

#### Response — `200 OK`

```json
{
    "document_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
    "message": "Document and 92 associated chunks have been removed.",
    "chunks_removed": 92
}
```

---

## 5. Create Session

### `POST /api/v1/sessions`

Session is scoped to the authenticated user (`user_id` stored at creation).

#### Request Body

```json
{
    "document_ids": [
        "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
    ]
}
```

Both `document_ids` and the entire body are optional.

#### Response — `201 Created`

```json
{
    "session_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
    "document_ids": ["a1b2c3d4-e5f6-7890-abcd-ef1234567890"],
    "created_at": "2026-04-12T10:40:00Z",
    "message": "Session created successfully."
}
```

---

## 6. Get Session

### `GET /api/v1/sessions/{session_id}`

Returns `404` if the session does not exist **or** belongs to a different user (ownership enforced; no information leak).

#### Response — `200 OK`

```json
{
    "session_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
    "document_ids": ["a1b2c3d4-e5f6-7890-abcd-ef1234567890"],
    "conversation_history": [
        {
            "turn_index": 0,
            "user_query": "What was Acme Corp's Q3 2024 revenue?",
            "standalone_query": "What was Acme Corp's Q3 2024 revenue?",
            "assistant_response": "According to the report, Q3 2024 revenue was $4.2 million [Source 1].",
            "citations": [
                {
                    "document_name": "annual_report_2024.pdf",
                    "page_numbers": [5],
                    "chunk_index": 12,
                    "chunk_id": "d4e5f6a7-...",
                    "excerpt": "Q3 2024 revenue reached $4.2 million..."
                }
            ],
            "timestamp": "2026-04-12T10:42:00Z"
        }
    ],
    "turn_count": 1,
    "created_at": "2026-04-12T10:40:00Z",
    "last_active_at": "2026-04-12T10:42:00Z"
}
```

---

## 7. Delete Session

### `DELETE /api/v1/sessions/{session_id}`

Returns `404` if session not found or belongs to another user.

#### Response — `200 OK`

```json
{
    "session_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
    "message": "Session deleted successfully.",
    "turns_cleared": 1
}
```

---

## 8. Query (Synchronous)

### `POST /api/v1/query`

| Field | Type | Required | Default | Constraints |
|---|---|---|---|---|
| `question` | string | Yes | — | 1–2000 characters |
| `session_id` | string (UUID) | Yes | — | Must exist and belong to caller |
| `document_ids` | list[string] | No | all session docs | Valid document UUIDs |
| `top_k` | int | No | 10 | 3–15 |

#### Request Body

```json
{
    "question": "What were the key risk factors?",
    "session_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
    "document_ids": ["a1b2c3d4-e5f6-7890-abcd-ef1234567890"],
    "top_k": 10
}
```

#### Response — `200 OK`

```json
{
    "answer": "The report identifies three key risk factors: (1) supply chain disruptions [Source 1], (2) EU regulatory compliance costs [Source 2], and (3) cybersecurity threats [Source 3].",
    "citations": [
        {
            "document_name": "annual_report_2024.pdf",
            "page_numbers": [32],
            "chunk_index": 67,
            "chunk_id": "b8c9d0e1-...",
            "excerpt": "Supply chain disruptions remain a primary concern..."
        },
        {
            "document_name": "annual_report_2024.pdf",
            "page_numbers": [33],
            "chunk_index": 69,
            "chunk_id": "c9d0e1f2-...",
            "excerpt": "Regulatory compliance costs are projected to increase by 20%..."
        },
        {
            "document_name": "annual_report_2024.pdf",
            "page_numbers": [34],
            "chunk_index": 71,
            "chunk_id": "d0e1f2a3-...",
            "excerpt": "The company experienced a 40% increase in attempted cyber intrusions..."
        }
    ],
    "session_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
    "query_id": "q-f2a3b4c5-d6e7-8901-lmno-012345678901",
    "confidence": 0.87,
    "retrieval_metadata": {
        "retrieval_time_ms": 62.4,
        "chunks_considered": 10,
        "chunks_used": 10,
        "hybrid_search_applied": true,
        "reranker_applied": false,
        "similarity_scores": [0.041, 0.038, 0.035, 0.031, 0.028]
    }
}
```

> **Note on similarity scores**: After RRF merge, scores are rank-fusion values (typically 0.005–0.05), not raw cosine similarities.

#### Error Responses

**404 — Session not found or unauthorised:**
```json
{"detail": "Session c3d4e5f6-... not found."}
```

**409 — No documents in session:**
```json
{"detail": "No documents associated with this session."}
```

**502 — OpenAI API failure:**
```json
{"detail": "Generation failed: upstream API error."}
```

---

## 9. Query (Streaming SSE)

### `POST /api/v1/query/stream`

Request body is identical to `POST /query`.

#### Response — `200 OK`

**Headers:**
```
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive
X-Query-Id: q-f2a3b4c5-...   (present only when available at header-write time)
```

**SSE Event Stream:**

```
event: token
data: {"text": "The", "query_id": "q-f2a3b4c5-..."}

event: token
data: {"text": " report", "query_id": "q-f2a3b4c5-..."}

...

event: citation
data: {"citations": [{"document_name": "annual_report_2024.pdf", "page_numbers": [32], "chunk_index": 67, "chunk_id": "b8c9d0e1-...", "excerpt": "Supply chain..."}], "query_id": "q-f2a3b4c5-..."}

event: done
data: {"query_id": "q-f2a3b4c5-...", "total_tokens": 89, "retrieval_time_ms": 62.4, "confidence": 0.87, "hybrid_search_applied": true, "reranker_applied": false}
```

**Error event (mid-stream failure):**
```
event: error
data: {"message": "Generation interrupted: OpenAI API timeout", "query_id": "q-f2a3b4c5-..."}
```

> **Note**: The `query_id` is always present in the `done` event body. The `X-Query-Id` header may be absent if `query_id` is not yet resolved when HTTP headers are written.

---

## 10. Health Check

### `GET /api/v1/health`

No authentication required.

#### Response — `200 OK` (healthy)

```json
{
    "status": "healthy",
    "version": "0.1.0",
    "checks": {
        "vector_store": "ok",
        "openai_api": "ok",
        "upload_dir": "ok"
    },
    "uptime_seconds": 3642.7,
    "active_sessions": 3,
    "total_documents": 12,
    "total_vectors": 1847
}
```

#### Response — `503 Service Unavailable` (unhealthy)

```json
{
    "status": "unhealthy",
    "version": "0.1.0",
    "checks": {
        "vector_store": "ok",
        "openai_api": "error",
        "upload_dir": "ok"
    },
    "uptime_seconds": 3642.7,
    "active_sessions": 3,
    "total_documents": 12,
    "total_vectors": 1847
}
```

---

## 11. Debug — Index Stats

### `GET /api/v1/debug/index`

Requires authentication.

#### Response — `200 OK`

```json
{
    "faiss_stats": {
        "total_vectors": 184,
        "total_documents": 3,
        "index_type": "pgvector/cosine",
        "dimensions": 1536
    },
    "registry_documents": [
        {"id": "a1b2c3d4-...", "name": "annual_report_2024.pdf", "status": "ready"}
    ],
    "faiss_document_ids": [],
    "threshold_in_use": null
}
```

---

## 12. Debug — Similarity Search

### `GET /api/v1/debug/search?q={query}&doc_id={doc_id}`

Requires authentication. Embeds the query using the shared `app.state.embedder` and returns raw similarity scores. Use this to diagnose retrieval issues.

| Parameter | Type | Required | Description |
|---|---|---|---|
| `q` | string | Yes | Query text to embed and search |
| `doc_id` | string (UUID) | No | Limit search to a specific document |

#### Response — `200 OK`

```json
{
    "query": "what is the revenue?",
    "threshold_in_config": 0.0,
    "total_vectors_in_index": 184,
    "results_found": 5,
    "results": [
        {
            "score": 0.2341,
            "document_id": "a1b2c3d4-...",
            "document_name": "annual_report_2024.pdf",
            "chunk_index": 12,
            "page_numbers": [5],
            "text_preview": "Q3 2024 revenue reached $4.2 million, representing a 15% increase..."
        }
    ]
}
```

> **Note on scores**: Raw cosine similarity from pgvector (`1 - cosine_distance`). Values of 0.10–0.29 indicate relevant matches with `text-embedding-3-small`. This endpoint bypasses RRF and MMR — it is purely for inspecting raw embedding similarity.

---

## Common Error Response Format

All error responses use FastAPI's default structure:

```json
{
    "detail": "Human-readable error message"
}
```

| HTTP Status | When |
|---|---|
| 400 | Invalid request (wrong file type, Google-only account, bad reset token) |
| 401 | Missing, expired, or logged-out JWT |
| 403 | Incorrect password |
| 404 | Resource not found or ownership mismatch (session/document) |
| 409 | Conflict (email already registered, no documents in session) |
| 422 | PDF parsing or chunking failure |
| 429 | Rate limit exceeded (token bucket per user) |
| 500 | Unexpected internal error |
| 501 | Feature not configured (Google OAuth without `GOOGLE_CLIENT_ID`) |
| 502 | OpenAI API failure |
| 504 | Embedding or generation timeout |
