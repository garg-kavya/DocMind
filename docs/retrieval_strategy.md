# Retrieval Strategy — DocMind

---

## Overview

Retrieval is a five-stage pipeline owned by `RAGPipeline` and executed by `RetrieverService`, `PGVectorStore`, and `RerankerService`:

```
EmbeddingCache.get_or_embed(standalone_query)
         │
         │  1536-dim query vector
         ▼
RetrieverService.retrieve(query_embedding, query_text, document_ids)
    │
    ├── Stage 1a: PGVectorStore.search()        cosine similarity (pgvector)
    │              over-fetch top-20 candidates, scoped to document_ids
    │
    ├── Stage 1b: PGVectorStore.keyword_search() PostgreSQL FTS (ts_rank_cd)
    │              plainto_tsquery('simple', …), scoped to document_ids
    │
    ├── Stage 2:  RRF merge                      rank fusion of both lists
    │
    └── Stage 3:  Score threshold filter         discard < SIMILARITY_THRESHOLD
          │                                      (default 0.0 = disabled)
          │  list[ScoredChunk]
          ▼
RerankerService.rerank(standalone_query, candidates)   [optional]
    │
    │  list[ScoredChunk] with similarity_score = reranker score
    ▼
RetrieverService.apply_mmr(candidates, top_k=10)
    │
    │  final top-k diverse, relevant chunks
    ▼
RAGChain.invoke(query_context, retrieved_context)
```

---

## Pre-Retrieval: Query Reformulation

Before any retrieval, `QueryReformulator` rewrites the raw query into a standalone, search-optimised form. This step **always runs** regardless of conversation history.

**Coreference resolution** — anchors follow-up queries to their referent:
> "What about their revenue?" → "What was Acme Corp's Q3 2024 revenue?"

**Inference/vague query expansion** — rewrites evaluation questions into concrete search terms:
> "Is he a bad guy?" → "professional misconduct unethical behaviour criminal record character flaws"
> "Should I hire her?" → "qualifications skills experience achievements suitability for role"

The `standalone_query` is embedded and passed to the vector store. For exact-match terms, the same text is used for keyword search.

---

## Stage 1a: Vector Similarity Search (pgvector)

- **Model**: OpenAI `text-embedding-3-small` (1536 dimensions)
- **Distance metric**: cosine distance (`<=>` operator), returned as `1 - cosine_distance`
- **Index**: `ivfflat` or `hnsw` via pgvector; exact ANN search within PostgreSQL
- **Scope**: `WHERE document_id = ANY($document_ids)` limits search to the current session's documents
- **Over-fetch**: retrieves `TOP_K_CANDIDATES = 20` candidates (= `TOP_K × 2`) so RRF and MMR have enough to work with

**Why cosine and not dot product?**
`text-embedding-3-small` embeddings are not L2-normalised. Cosine distance explicitly accounts for vector magnitude, giving consistent scores regardless of embedding scale.

---

## Stage 1b: Keyword Search (PostgreSQL FTS)

- **Column**: `text_search tsvector GENERATED ALWAYS AS (to_tsvector('simple', text)) STORED`
- **Query**: `plainto_tsquery('simple', standalone_query)` — no stemming, matches tokens verbatim
- **Scoring**: `ts_rank_cd(text_search, query)` — normalised to [0, 1] before returning
- **Why `'simple'` dictionary?** Preserves exact tokens: serial numbers, model codes, IDs, and proper nouns that stemming would distort

FTS recovers chunks that score low on embeddings but contain literal matches — a critical supplement for technical documents, CVs, and tables.

---

## Stage 2: RRF Merge (Reciprocal Rank Fusion)

Both ranked lists (cosine and FTS) are merged using Reciprocal Rank Fusion:

```
rrf_score(chunk) = Σ  1 / (k + rank_in_list + 1)
                  lists

k = 60  (standard constant from the original RRF paper)
```

Each chunk accumulates score from every list it appears in. Chunks ranked highly in both lists score highest. Chunks unique to one list are included but rank lower.

After merging, chunks are deduplicated by `chunk_id` and sorted by `rrf_score` descending. The merged `rrf_score` becomes the `similarity_score` for downstream stages.

**Effect**: exact-match terms and semantic matches are both surfaced. A query like "Revenue Q3 2024" benefits from both the embedding similarity to financial context *and* the literal FTS match on "Revenue", "Q3", "2024".

---

## Stage 3: Score Threshold Filtering

**Default**: `SIMILARITY_THRESHOLD = 0.0` (disabled — all candidates proceed)

With `text-embedding-3-small`, cosine similarity for semantically related but not near-identical text typically falls in the **0.10–0.29** range. After RRF, scores are rank-fusion values (typically 0.005–0.05) rather than raw cosine values.

Calibration guide (cosine scores, pre-RRF):

| Range | Interpretation |
|---|---|
| > 0.30 | Very strong lexical overlap |
| 0.20–0.30 | Clear semantic match |
| 0.10–0.20 | Relevant match (typical for good retrieval) |
| 0.05–0.10 | Marginal |
| < 0.05 | Likely unrelated |

---

## Stage 4: Cross-Encoder Reranking (optional)

**Purpose**: Improve relevance ordering. A bi-encoder scores query and chunk independently; a cross-encoder reads both together for fundamentally more accurate relevance judgement.

**Backends**:

| Backend | Latency | Quality | Use case |
|---|---|---|---|
| `none` (default) | 0ms | — | Rely on RRF + MMR ordering |
| `cross_encoder` | 50–150ms | High | Local model, no cost, dev/private |
| `cohere` | 200–400ms | Highest | Production, external API |

**Score contract**:
- Input: `similarity_score == rrf_score`
- Output: `rerank_score` = raw cross-encoder / Cohere score; `similarity_score` = normalised reranker score; `bi_encoder_score` preserved for diagnostics

**Failure handling**: `RerankerError` → warning logged, fallback to bi-encoder order. The request never fails due to a reranker error.

---

## Stage 5: MMR Diversity Selection

MMR (Maximal Marginal Relevance) prevents the top-k from being near-identical adjacent chunks from the same paragraph.

**Formula**:
```
score(chunk_i) = λ · similarity_score(chunk_i, query)
               − (1−λ) · max over selected{diversity_penalty(chunk_i, chunk_j)}
```

**Diversity signal** (chunk position distance):
- Same document: `penalty = 1 / (1 + |chunk_index_i − chunk_index_j|)`
  → adjacent chunks (distance ≤ 1) penalised heavily; distant chunks allowed
- Different document: `penalty = 0.0` — cross-document pairs are maximally diverse

**λ = `MMR_DIVERSITY_FACTOR` = 0.7** — favours relevance with mild diversity pressure

**Skip condition**: if `len(candidates) ≤ top_k`, all candidates pass through unmodified (no diversity gain possible with fewer candidates than the budget).

After MMR, each chunk has `rank` set (1-based). This is the final ordering passed to the LLM in the context block.

---

## Chunk Size Analysis

| Size | Semantic quality | Context | Est. P@10 | 10-chunk context cost |
|---|---|---|---|---|
| 256 tokens | Low — splits mid-idea | Poor | ~0.45–0.55 | 2,560 tokens |
| 384 tokens | Moderate | Moderate | ~0.55–0.65 | 3,840 tokens |
| **512 tokens** | **High — 1–2 paragraphs** | **Good** | **~0.70–0.82** | **5,120 tokens** |
| 768 tokens | Mixed topics in one chunk | Broad | ~0.58–0.68 | 7,680 tokens |
| 1024 tokens | Diluted embedding signal | Very broad | ~0.45–0.55 | 10,240 tokens |

**Selected: 512 tokens**

1. Large enough to contain a complete idea with supporting context
2. Small enough for the embedding to represent one focused concept
3. 10 × 512 = 5,120 tokens leaves room for system prompt (~200), history (~1,024), and generation (~1,024) within a 16K context window

**Overlap: 64 tokens (12.5%)** — boundary sentences appear in both adjacent chunks, preventing information loss at splits.

**Split hierarchy**: `\n\n` → `\n` → `". "` → `" "` — always splits at the highest-level semantic boundary that keeps the chunk within the token budget.

---

## Top-K Tuning

| k | Use case | Notes |
|---|---|---|
| 3 | Simple factual lookup | Fast, minimal context |
| 5 | Narrow Q&A | Lower noise |
| **10** | **General Q&A (default)** | **Best balance; handles inference queries** |
| 15 | Synthesis / summarisation | Maximum coverage, more noise |

The higher default (10) is intentional. Inference queries ("Is he a good candidate?") need broader evidence coverage to draw conclusions from sparse signal. Per-query override via the `top_k` API parameter (range 3–15).

---

## Expected Precision@10 by Configuration

| Configuration | Estimated P@10 |
|---|---|
| 512t, k=10, no reranker, no MMR | 0.50–0.60 |
| 512t, k=10, no reranker, MMR only | 0.60–0.70 |
| 512t, k=10, hybrid (RRF), MMR | 0.65–0.75 |
| 512t, k=10, hybrid + cross-encoder, MMR | **0.72–0.84** |
| 512t, k=10, hybrid + Cohere, MMR | **0.76–0.88** |

---

## Latency by Configuration

| Configuration | Retrieval latency | Total to first token |
|---|---|---|
| pgvector only, no reranker | ~50ms | ~750–1050ms |
| pgvector + FTS + RRF, no reranker | ~70ms | ~770–1070ms |
| pgvector + FTS + RRF + cross-encoder | ~220ms | ~920–1220ms |
| pgvector + FTS + RRF + Cohere | ~420ms | ~1120–1420ms |

All configurations remain within the 2-second target for time to first token.

---

## Hybrid Search vs Vector-Only

| Query type | Vector only | Hybrid (RRF) |
|---|---|---|
| Semantic / paraphrased | ✓ Strong | ✓ Strong |
| Exact term (ID, code, name) | ✗ Often misses | ✓ FTS recovers it |
| Mixed (concept + term) | Partial | ✓ Both signals combined |
| Very short query (1–2 words) | Weak embedding signal | ✓ FTS term match helps |

The hybrid approach is strictly better or equal to vector-only in all cases. The only cost is the additional FTS query (~3–20ms) and RRF merge (~1ms).
