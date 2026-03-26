"""Reranking Service — cross-encoder second-pass relevance scoring."""
from __future__ import annotations

from app.config import Settings
from app.exceptions import RerankerError
from app.models.query import ScoredChunk
from app.utils.logging import get_logger

logger = get_logger(__name__)


class RerankerService:

    def __init__(self, settings: Settings) -> None:
        self._backend = settings.reranker_backend
        self._cohere_key = settings.cohere_api_key
        self._cross_encoder_model = settings.cross_encoder_model
        self._cross_encoder = None  # lazy load

    def is_enabled(self) -> bool:
        return self._backend != "none"

    async def rerank(
        self,
        query_text: str,
        candidates: list[ScoredChunk],
    ) -> list[ScoredChunk]:
        """Re-score candidates; return sorted by reranker score descending."""
        if not candidates:
            return candidates
        if len(candidates) == 1:
            return candidates

        try:
            if self._backend == "cohere":
                return await self._rerank_cohere(query_text, candidates)
            elif self._backend == "cross_encoder":
                return self._rerank_cross_encoder(query_text, candidates)
            else:
                return candidates
        except RerankerError:
            raise
        except Exception as exc:
            raise RerankerError(f"Reranker ({self._backend}) failed: {exc}") from exc

    async def _rerank_cohere(
        self, query_text: str, candidates: list[ScoredChunk]
    ) -> list[ScoredChunk]:
        import cohere

        if not self._cohere_key:
            raise RerankerError("COHERE_API_KEY is not configured.")

        co = cohere.AsyncClientV2(api_key=self._cohere_key)
        docs = [sc.chunk.text for sc in candidates]
        response = await co.rerank(
            model="rerank-english-v3.0",
            query=query_text,
            documents=docs,
            top_n=len(candidates),
        )

        max_score = max((r.relevance_score for r in response.results), default=1.0)
        max_score = max_score or 1.0

        reranked = list(candidates)
        for r in response.results:
            sc = reranked[r.index]
            sc.rerank_score = r.relevance_score
            sc.similarity_score = r.relevance_score / max_score  # normalize to [0,1]

        reranked.sort(key=lambda sc: sc.rerank_score or 0, reverse=True)
        return reranked

    def _rerank_cross_encoder(
        self, query_text: str, candidates: list[ScoredChunk]
    ) -> list[ScoredChunk]:
        from sentence_transformers import CrossEncoder

        if self._cross_encoder is None:
            self._cross_encoder = CrossEncoder(self._cross_encoder_model)

        pairs = [(query_text, sc.chunk.text) for sc in candidates]
        scores = self._cross_encoder.predict(pairs)

        max_score = max(scores) if len(scores) > 0 else 1.0
        max_score = max_score or 1.0

        for sc, raw_score in zip(candidates, scores):
            sc.rerank_score = float(raw_score)
            sc.similarity_score = float(raw_score) / float(max_score)

        candidates.sort(key=lambda sc: sc.rerank_score or 0, reverse=True)
        return candidates
