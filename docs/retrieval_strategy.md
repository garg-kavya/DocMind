# Retrieval Strategy — RAG PDF Q&A System

This document provides the detailed design rationale for the retrieval pipeline, including chunk size selection, top-k tuning, and ranking strategy.

---

## 1. Chunking Strategy

### The Problem

PDF documents contain continuous text that must be split into discrete units for embedding and retrieval. The chunk size is the single most impactful parameter for retrieval quality.

### Chunk Size Analysis

| Chunk Size | Pros | Cons | Precision@5 Impact |
|---|---|---|---|
| **256 tokens** | High specificity per chunk | Fragments coherent ideas; loses surrounding context; retrieval becomes noisy because relevant info scatters across many small chunks | Lower — too many near-miss chunks pollute top-5 |
| **384 tokens** | Good specificity | Still splits many paragraphs mid-thought | Moderate |
| **512 tokens** | Contains 1-2 complete paragraphs; strong semantic coherence; embedding captures a focused but complete idea | May occasionally include tangential sentences | **Highest** — best balance of signal and noise |
| **768 tokens** | Broader context per chunk | Mixed topics in one chunk dilute embedding signal | Moderate — relevance signal weakened |
| **1024 tokens** | Maximum context per chunk | Multiple topics per chunk; embedding is blurred average; fewer chunks fit in LLM context | Lower — chunks too broad for precise matching |

### Selected: 512 Tokens

**Rationale:**

1. **Semantic coherence:** 512 tokens typically covers 1-2 paragraphs in academic/business PDFs. This is large enough to contain a complete idea with supporting detail, but small enough that the embedding vector represents a focused concept.

2. **Context budget:** With top-k=5, the total context is 5 × 512 = 2,560 tokens. Combined with the system prompt (~200 tokens), conversation history (~500 tokens), and generation budget (1,024 tokens), the total fits comfortably within a 4K or 8K context window. This leaves room for comprehensive answers without truncation.

3. **Embedding quality:** OpenAI's embedding models produce the highest-quality vectors when the input is focused on a single topic. 512 tokens is the empirical sweet spot for this — long enough for context, short enough for focus.

4. **Overlap (64 tokens / 12.5%):** Ensures sentences at chunk boundaries appear in both adjacent chunks. If a query matches a boundary sentence, at least one chunk will retrieve it. The 12.5% ratio avoids excessive storage overhead.

### Splitting Hierarchy

Text is split using a priority hierarchy of separators:

```
1. "\n\n"  — Paragraph break (strongest semantic boundary)
2. "\n"    — Line break
3. ". "    — Sentence boundary
4. " "     — Word boundary (last resort)
```

The chunker attempts to split at the highest-priority boundary that keeps the chunk within the token budget. This ensures:
- Paragraphs are never split mid-sentence if they fit in one chunk
- Long paragraphs split at sentence boundaries, not mid-word
- The resulting chunks are maximally aligned with the document's semantic structure

---

## 2. Embedding Strategy

### Model Selection

**text-embedding-3-small** (OpenAI)
- 1536 dimensions
- Output vectors are L2-normalized (unit length)
- Cosine similarity reduces to dot product on normalized vectors
- Strong MTEB benchmark scores for retrieval tasks
- Cost: ~$0.02 per 1M tokens

**Why not text-embedding-3-large (3072 dims)?**
- 2× vector storage cost
- Marginal quality improvement for typical PDF content
- Configurable for users who need maximum precision

### Query vs. Document Embedding

The same model is used for both document chunks and queries. This is critical — cross-model embedding produces misaligned vector spaces and degrades retrieval quality.

---

## 3. Retrieval Pipeline

The retrieval pipeline uses a **3-stage approach** to maximize precision@5:

```
Query Embedding
      │
      ▼
┌──────────────────────┐
│ Stage 1: VECTOR      │  Retrieve top_k × 2 candidates (10 by default)
│ SIMILARITY SEARCH    │  Cosine similarity on normalized vectors
│                      │  Scoped to session's document_ids
│ Latency: 10-50ms    │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ Stage 2: SCORE       │  Remove chunks with score < 0.70
│ THRESHOLD FILTER     │  Prevents irrelevant chunks from reaching LLM
│                      │  May return fewer than top_k results
│ Latency: <1ms       │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────┐
│ Stage 3: MMR         │  Select final top_k from filtered candidates
│ RE-RANKING           │  Balance relevance (70%) vs diversity (30%)
│                      │  Eliminates near-duplicate chunks
│ Latency: 5-20ms     │
└──────────┬───────────┘
           │
           ▼
     Top-K Results
```

### Stage 1: Vector Similarity Search

- **Algorithm:** Exhaustive cosine similarity (FAISS IndexFlatIP)
- **Over-fetch factor:** 2× top_k to provide candidates for re-ranking
- **Document scoping:** Only search within the session's document_ids
  - FAISS: post-filter after search (over-fetch 3× for safety)
  - ChromaDB: native `where={"document_id": {"$in": [...]}}` filter

### Stage 2: Score Threshold

- **Threshold:** 0.70 (configurable via SIMILARITY_THRESHOLD)
- **Purpose:** Hard quality floor — even if the user asks for k=10, chunks below 0.70 are excluded
- **Calibration:** With text-embedding-3-small on PDF content:
  - 0.80+: Very strong semantic match (same topic, same subtopic)
  - 0.70-0.80: Relevant (same topic, related subtopic)
  - 0.60-0.70: Marginal (same domain, different topic)
  - <0.60: Irrelevant
- **Effect on precision@5:** Eliminates the "padding" problem where low-relevance chunks fill out the top-k when the document doesn't contain enough truly relevant content

### Stage 3: MMR Re-Ranking

**Maximal Marginal Relevance** selects chunks that are both relevant to the query AND different from each other.

```
score(chunk_i) = λ × sim(chunk_i, query)
               - (1 - λ) × max(sim(chunk_i, already_selected_j))
```

- **λ = 0.7** (MMR_DIVERSITY_FACTOR in config)
  - 70% weight on relevance, 30% on diversity
  - Favors relevant chunks but penalizes redundancy

- **Why MMR matters for PDF Q&A:**
  PDF documents often contain repeated information (executive summary + detail section, table of contents + full text). Without MMR, the top-5 might be 5 chunks all saying the same thing from different locations. MMR ensures the 5 chunks cover different aspects of the answer.

- **Effect on precision@5:** Increases information coverage per retrieved set, directly improving answer completeness.

---

## 4. Top-K Tuning

### Default: k=5

| k Value | Use Case | Trade-off |
|---|---|---|
| **k=3** | Simple factual lookup ("What is X?") | Fast, precise, but may miss supporting evidence |
| **k=5** | General Q&A (default) | Best balance — covers main answer + supporting detail |
| **k=7** | Analytical questions ("Compare X and Y") | Broader coverage, more LLM context consumed |
| **k=10** | Synthesis questions ("Summarize all findings") | Maximum coverage, risk of noise, slow |

### Why 5 is the Default

1. **Context budget:** 5 × 512 = 2,560 tokens of context. This leaves ~1,440 tokens for prompt + history + generation in a 4K window, or ~5,440 tokens in an 8K window. Ample for detailed answers.

2. **Diminishing returns:** In benchmarks on factual PDF Q&A, precision plateaus after k=5. Additional chunks add noise faster than they add relevant information.

3. **Latency:** More chunks = more tokens in the LLM prompt = longer generation time. k=5 keeps generation fast.

4. **Per-query override:** The API allows overriding top_k per request (range 3-10), so users can tune for their specific question type.

---

## 5. Performance: How Latency <2s is Achieved

### Latency Breakdown (Query Path)

| Stage | Technique | Latency |
|---|---|---|
| Session lookup | In-memory dict | <1ms |
| Query reformulation | gpt-4o-mini (small, fast) | 0-400ms |
| Query embedding | Single OpenAI API call | 100-150ms |
| Vector search | FAISS in-memory (no network) | 10-50ms |
| Threshold + MMR | CPU-only computation | 5-20ms |
| LLM first token | OpenAI streaming (stream=True) | 300-500ms |
| **Total to first token** | | **~650-1200ms** |

### Key Optimizations

1. **Pre-computed document embeddings:** All chunk embeddings are computed during ingestion. Zero embedding computation at query time for documents.

2. **FAISS in-memory index:** No network hop for vector search. Sub-50ms for typical workloads (1K-100K vectors).

3. **Streaming generation:** The client sees the first token in <1.2s. Full answer streams over 2-5 seconds, but perceived latency is the time to first token.

4. **Conditional reformulation:** First-turn queries skip the reformulation step entirely, saving 200-400ms.

5. **Fast reformulation model:** Follow-ups use gpt-4o-mini (not gpt-4o) for reformulation — it's a simple rewriting task that doesn't need the full model.

6. **Connection pooling:** httpx.AsyncClient maintains persistent connections to OpenAI's API, eliminating TCP/TLS handshake overhead on every call.

### Worst-Case Analysis

Even in the worst case (follow-up question, slow API responses):
- Reformulation: 600ms
- Embedding: 300ms
- Retrieval: 100ms
- First token: 800ms
- **Total: 1,800ms** — still under the 2-second target.

---

## 6. How Chunking + Top-K Improves Precision@5

**Precision@5** = (relevant chunks in top 5) / 5

### The Interaction

Chunk size and top-k are not independent — they interact:

1. **Smaller chunks + higher k:** More granular retrieval. Each chunk is highly focused, but you need more of them to cover the answer. Risk: individual chunks lack context.

2. **Larger chunks + lower k:** Fewer but broader chunks. Each chunk covers more ground, but the embedding is less focused. Risk: irrelevant content mixed in.

3. **512 chunks + k=5 (our choice):** Each chunk is focused enough for precise embedding, but large enough to contain a complete thought. 5 chunks cover the answer from multiple angles without excessive noise.

### Additional Precision Boosters

- **Overlap (64 tokens):** Ensures boundary sentences are retrievable, preventing precision loss from unlucky chunk splits.
- **Score threshold (0.70):** Removes irrelevant chunks even if k requests more, preventing noise from dragging down precision.
- **MMR diversity:** Ensures the 5 chunks aren't redundant copies of the same information, maximizing information coverage per position in the top-5.
- **Query reformulation:** Follow-up queries become precise standalone questions, producing higher-quality embeddings that match more accurately.

### Expected Precision@5 by Configuration

| Config | Expected P@5 | Notes |
|---|---|---|
| 256 tokens, k=5, no MMR | 0.45-0.55 | Fragmented chunks, redundant results |
| 512 tokens, k=5, no MMR | 0.60-0.70 | Good chunks, but redundancy |
| 512 tokens, k=5, MMR | **0.70-0.85** | **Our config — best balance** |
| 1024 tokens, k=5, MMR | 0.55-0.65 | Chunks too broad, diluted signal |
| 512 tokens, k=10, MMR | 0.50-0.60 | Too many results, noise increases |

These are estimates based on typical PDF Q&A benchmarks. Actual performance depends on document content and question distribution. Use `scripts/benchmark.py` to measure on your specific workload.
