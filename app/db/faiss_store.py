"""FAISS vector store implementation."""
from __future__ import annotations

import asyncio
import json
import os
from typing import Any

import numpy as np

from app.db.vector_store import VectorStore
from app.exceptions import IndexNotFoundError, StorageReadError, StorageWriteError
from app.models.chunk import Chunk
from app.utils.logging import get_logger

logger = get_logger(__name__)


class FAISSStore(VectorStore):
    """In-memory FAISS IndexFlatIP with parallel metadata dict."""

    def __init__(self, dimensions: int = 1536, persist_path: str | None = None) -> None:
        self._dimensions = dimensions
        self._persist_path = persist_path
        self._index: Any = None          # faiss.IndexFlatIP
        self._metadata: dict[int, dict] = {}  # faiss_id → chunk metadata
        self._next_id: int = 0
        self._lock = asyncio.Lock()
        self._init_index()

    def _init_index(self) -> None:
        import faiss  # lazy import so the module loads without faiss installed
        self._index = faiss.IndexFlatIP(self._dimensions)

    # ------------------------------------------------------------------
    # VectorStore interface
    # ------------------------------------------------------------------

    async def add_chunks(self, chunks: list[Chunk]) -> None:
        if not chunks:
            return
        vectors = []
        metas = []
        for chunk in chunks:
            if chunk.embedding is None:
                raise StorageWriteError(
                    f"Chunk {chunk.chunk_id} has no embedding.",
                    detail="embed_chunks must be called before add_chunks",
                )
            vectors.append(chunk.embedding)
            metas.append(chunk.metadata)

        matrix = np.array(vectors, dtype=np.float32)
        # Normalize to unit L2 for cosine similarity via inner product
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)
        matrix = matrix / norms

        async with self._lock:
            try:
                self._index.add(matrix)
                for meta in metas:
                    self._metadata[self._next_id] = meta
                    self._next_id += 1
            except Exception as exc:
                raise StorageWriteError(f"FAISS add failed: {exc}") from exc

        logger.info("Added %d vectors to FAISS index", len(chunks))

    async def search(
        self,
        query_embedding: list[float],
        top_k: int,
        document_ids: list[str] | None = None,
    ) -> list[tuple[Chunk, float]]:
        async with self._lock:
            if self._index.ntotal == 0:
                return []

            # When filtering by document_ids, fetch ALL vectors so the
            # document filter doesn't silently exclude the target doc's chunks
            # (they may not rank in the global top-K if other docs dominate).
            fetch_k = self._index.ntotal if document_ids else top_k
            fetch_k = max(fetch_k, top_k)  # always fetch at least top_k

            q = np.array([query_embedding], dtype=np.float32)
            norm = np.linalg.norm(q)
            if norm > 0:
                q = q / norm

            try:
                scores, ids = self._index.search(q, fetch_k)
            except Exception as exc:
                raise StorageReadError(f"FAISS search failed: {exc}") from exc

            results: list[tuple[Chunk, float]] = []
            for faiss_id, score in zip(ids[0], scores[0]):
                if faiss_id < 0:
                    continue
                meta = self._metadata.get(int(faiss_id))
                if meta is None:
                    continue
                if document_ids and meta["document_id"] not in document_ids:
                    continue
                chunk = self._meta_to_chunk(meta)
                results.append((chunk, float(score)))
                if len(results) >= top_k:
                    break

        return results

    async def delete_document(self, document_id: str) -> int:
        async with self._lock:
            to_delete = [
                fid for fid, meta in self._metadata.items()
                if meta["document_id"] == document_id
            ]
            for fid in to_delete:
                del self._metadata[fid]
            # Note: FAISS IndexFlatIP doesn't support in-place deletion;
            # rebuild index from remaining metadata on next restart if needed.
            return len(to_delete)

    async def get_collection_stats(self) -> dict:
        async with self._lock:
            doc_ids = {m["document_id"] for m in self._metadata.values()}
            return {
                "total_vectors": self._index.ntotal,
                "total_documents": len(doc_ids),
                "index_type": "IndexFlatIP",
                "dimensions": self._dimensions,
            }

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    async def save_to_disk(self) -> None:
        if not self._persist_path:
            return
        import faiss
        os.makedirs(self._persist_path, exist_ok=True)
        index_path = os.path.join(self._persist_path, "faiss.index")
        meta_path = os.path.join(self._persist_path, "faiss_meta.json")
        async with self._lock:
            faiss.write_index(self._index, index_path)
            with open(meta_path, "w") as f:
                json.dump({"metadata": self._metadata, "next_id": self._next_id}, f)

    async def load_from_disk(self) -> None:
        if not self._persist_path:
            return
        import faiss
        index_path = os.path.join(self._persist_path, "faiss.index")
        meta_path = os.path.join(self._persist_path, "faiss_meta.json")
        if not os.path.exists(index_path):
            return
        async with self._lock:
            self._index = faiss.read_index(index_path)
            with open(meta_path) as f:
                data = json.load(f)
            self._metadata = {int(k): v for k, v in data["metadata"].items()}
            self._next_id = data["next_id"]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _meta_to_chunk(meta: dict) -> Chunk:
        return Chunk(
            chunk_id=meta["chunk_id"],
            document_id=meta["document_id"],
            document_name=meta["document_name"],
            chunk_index=meta["chunk_index"],
            text=meta["text"],
            token_count=meta["token_count"],
            page_numbers=meta["page_numbers"],
            start_char_offset=0,
            end_char_offset=0,
        )
