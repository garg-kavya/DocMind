"""Query API request/response schemas."""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    session_id: str
    document_ids: list[str] | None = None
    top_k: int | None = Field(None, ge=3, le=10)
    stream: bool = False

    @field_validator("question")
    @classmethod
    def question_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("question must not be blank")
        return v.strip()


class CitationSchema(BaseModel):
    document_name: str
    page_numbers: list[int]
    chunk_index: int
    chunk_id: str
    excerpt: str


class RetrievalMetadataSchema(BaseModel):
    retrieval_time_ms: float
    candidates_considered: int
    candidates_after_threshold: int
    chunks_used: int
    mmr_applied: bool
    reranker_applied: bool
    similarity_scores: list[float]
    top_k_requested: int
    similarity_threshold_used: float


class PipelineMetadataSchema(BaseModel):
    total_time_ms: float
    reformulation_time_ms: float
    embedding_time_ms: float
    retrieval_time_ms: float
    reranking_time_ms: float
    mmr_time_ms: float
    generation_time_ms: float
    memory_read_time_ms: float
    memory_write_time_ms: float
    embedding_cache_hit: bool
    response_cache_hit: bool
    reranker_backend: str
    llm_model: str
    embedding_model: str


class QueryResponse(BaseModel):
    answer: str
    citations: list[CitationSchema]
    session_id: str
    query_id: str
    confidence: float
    cache_hit: bool
    retrieval_metadata: RetrievalMetadataSchema | None = None
    pipeline_metadata: PipelineMetadataSchema | None = None


class StreamingChunkSchema(BaseModel):
    event: str
    data: str
    query_id: str
