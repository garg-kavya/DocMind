"""
Diagnostic: test raw cosine similarity between a query and sample text.
Helps understand if SIMILARITY_THRESHOLD=0.0 is the right fix.

Usage: python scripts/diagnose_similarity.py
"""
from __future__ import annotations

import asyncio
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


async def main() -> None:
    from app.config import get_settings
    from app.services.embedder import EmbedderService

    settings = get_settings()
    embedder = EmbedderService(settings)

    # Sample texts that might appear in an academic/course PDF
    sample_texts = [
        "Machine learning is a subset of artificial intelligence.",
        "Introduction to Computer Science module one lecture notes.",
        "Data structures and algorithms are fundamental concepts.",
        "The gradient descent algorithm is used in neural networks.",
        "This chapter covers basic programming concepts and syntax.",
    ]
    queries = [
        "What is machine learning?",
        "What topics are covered in this module?",
        "Explain gradient descent.",
    ]

    print("Embedding sample texts...")
    text_vectors = await embedder._embed_texts(sample_texts)

    print("Embedding queries...")
    query_vectors = await embedder._embed_texts(queries)

    import numpy as np

    def cosine_sim(a: list[float], b: list[float]) -> float:
        a_np = np.array(a)
        b_np = np.array(b)
        return float(np.dot(a_np, b_np) / (np.linalg.norm(a_np) * np.linalg.norm(b_np)))

    print("\n=== Raw cosine similarity scores ===\n")
    for q, qv in zip(queries, query_vectors):
        print(f"Query: {q!r}")
        for t, tv in zip(sample_texts, text_vectors):
            score = cosine_sim(qv, tv)
            flag = " *** ABOVE 0.30 ***" if score >= 0.30 else " (below 0.30)"
            print(f"  {score:.4f}{flag}  | {t[:60]}")
        print()

    print(f"\nCurrent SIMILARITY_THRESHOLD in .env: {settings.similarity_threshold}")
    if settings.similarity_threshold > 0.0:
        print("WARNING: Threshold > 0.0 may be filtering out valid results.")
        print("         Set SIMILARITY_THRESHOLD=0.0 in .env to disable filtering.")
    else:
        print("OK: Threshold is 0.0 — all candidates pass through.")


if __name__ == "__main__":
    asyncio.run(main())
