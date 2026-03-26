"""Tests for InMemoryCache, EmbeddingCache, and ResponseCache."""
from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock

import pytest

from app.cache.embedding_cache import EmbeddingCache
from app.cache.in_memory_cache import InMemoryCache
from app.cache.response_cache import ResponseCache
from app.models.query import GeneratedAnswer, PipelineMetadata


# ===========================================================================
# InMemoryCache
# ===========================================================================

@pytest.fixture
def cache() -> InMemoryCache:
    return InMemoryCache(max_size=5, default_ttl=60)


async def test_set_and_get(cache):
    await cache.set("key1", "value1")
    assert await cache.get("key1") == "value1"


async def test_get_missing_key_returns_none(cache):
    assert await cache.get("nonexistent") is None


async def test_ttl_expiry(cache):
    short_cache = InMemoryCache(max_size=10, default_ttl=1)
    await short_cache.set("k", "v", ttl_seconds=1)
    assert await short_cache.get("k") == "v"
    await asyncio.sleep(1.1)
    assert await short_cache.get("k") is None


async def test_delete_removes_key(cache):
    await cache.set("key", "value")
    await cache.delete("key")
    assert await cache.get("key") is None


async def test_delete_nonexistent_is_noop(cache):
    await cache.delete("ghost")  # should not raise


async def test_exists_true_for_set_key(cache):
    await cache.set("x", 42)
    assert await cache.exists("x") is True


async def test_exists_false_for_missing_key(cache):
    assert await cache.exists("missing") is False


async def test_clear_empties_cache(cache):
    await cache.set("a", 1)
    await cache.set("b", 2)
    await cache.clear()
    assert await cache.get("a") is None
    assert await cache.get("b") is None


async def test_lru_eviction_when_full(cache):
    # Fill to max_size (5)
    for i in range(5):
        await cache.set(f"k{i}", i)
    # Access k0 to make it recently used
    await cache.get("k0")
    # Add a 6th item — should evict k1 (LRU)
    await cache.set("k5", 5)
    assert await cache.get("k1") is None  # evicted
    assert await cache.get("k0") is not None  # recently used, kept


async def test_stats_counts_hits_and_misses(cache):
    await cache.set("x", 1)
    await cache.get("x")   # hit
    await cache.get("x")   # hit
    await cache.get("y")   # miss

    stats = await cache.stats()
    assert stats["hits"] == 2
    assert stats["misses"] == 1
    assert stats["sets"] == 1


async def test_stats_current_size(cache):
    await cache.set("a", 1)
    await cache.set("b", 2)
    stats = await cache.stats()
    assert stats["current_size"] == 2


# ===========================================================================
# EmbeddingCache
# ===========================================================================

@pytest.fixture
def backend() -> InMemoryCache:
    return InMemoryCache(max_size=100, default_ttl=3600)


@pytest.fixture
def mock_embedder_service():
    svc = AsyncMock()
    svc.embed_query = AsyncMock(return_value=[0.1] * 1536)
    return svc


@pytest.fixture
def embedding_cache(backend, mock_embedder_service) -> EmbeddingCache:
    return EmbeddingCache(backend=backend, embedder=mock_embedder_service, ttl=3600)


async def test_embed_cache_miss_calls_embedder(embedding_cache, mock_embedder_service):
    await embedding_cache.get_or_embed("What is AI?")
    mock_embedder_service.embed_query.assert_called_once_with("What is AI?")


async def test_embed_cache_hit_skips_embedder(embedding_cache, mock_embedder_service):
    await embedding_cache.get_or_embed("What is AI?")
    await embedding_cache.get_or_embed("What is AI?")
    assert mock_embedder_service.embed_query.call_count == 1


async def test_embed_key_normalisation(embedding_cache, mock_embedder_service):
    await embedding_cache.get_or_embed("What is AI?")
    await embedding_cache.get_or_embed("  what is ai?  ")  # normalised same key
    assert mock_embedder_service.embed_query.call_count == 1


async def test_embed_invalidate_clears_entry(embedding_cache, mock_embedder_service):
    await embedding_cache.get_or_embed("query")
    await embedding_cache.invalidate("query")
    await embedding_cache.get_or_embed("query")  # should call embedder again
    assert mock_embedder_service.embed_query.call_count == 2


async def test_embed_returns_vector(embedding_cache):
    vec = await embedding_cache.get_or_embed("test query")
    assert isinstance(vec, list)
    assert len(vec) == 1536


# ===========================================================================
# ResponseCache
# ===========================================================================

def _make_answer(query_id: str | None = None) -> GeneratedAnswer:
    qid = query_id or str(uuid.uuid4())
    return GeneratedAnswer(
        answer_text="Test answer",
        citations=[],
        confidence=0.9,
        query_id=qid,
        cache_hit=False,
        retrieval_context=None,
        pipeline_metadata=PipelineMetadata(query_id=qid),
    )


@pytest.fixture
def resp_cache() -> ResponseCache:
    return ResponseCache(backend=InMemoryCache(max_size=100, default_ttl=60), ttl=60)


async def test_response_cache_miss_calls_generate_fn(resp_cache):
    generate_fn = AsyncMock(return_value=_make_answer())
    await resp_cache.get_or_generate("q", "s1", ["doc1"], 0, generate_fn)
    generate_fn.assert_called_once()


async def test_response_cache_hit_skips_generate_fn(resp_cache):
    generate_fn = AsyncMock(return_value=_make_answer())
    await resp_cache.get_or_generate("q", "s1", ["doc1"], 0, generate_fn)
    await resp_cache.get_or_generate("q", "s1", ["doc1"], 0, generate_fn)
    generate_fn.assert_called_once()


async def test_response_cache_hit_flag_set(resp_cache):
    generate_fn = AsyncMock(return_value=_make_answer())
    await resp_cache.get_or_generate("q", "s1", ["doc1"], 0, generate_fn)
    answer2 = await resp_cache.get_or_generate("q", "s1", ["doc1"], 0, generate_fn)
    assert answer2.cache_hit is True
    assert answer2.pipeline_metadata.response_cache_hit is True


async def test_response_fresh_answer_cache_hit_false(resp_cache):
    generate_fn = AsyncMock(return_value=_make_answer())
    answer = await resp_cache.get_or_generate("q", "s1", ["doc1"], 0, generate_fn)
    assert answer.cache_hit is False


async def test_response_turn_count_change_causes_miss(resp_cache):
    generate_fn = AsyncMock(return_value=_make_answer())
    await resp_cache.get_or_generate("q", "s1", ["doc1"], 0, generate_fn)
    await resp_cache.get_or_generate("q", "s1", ["doc1"], 1, generate_fn)  # different turn
    assert generate_fn.call_count == 2


async def test_response_different_query_causes_miss(resp_cache):
    generate_fn = AsyncMock(return_value=_make_answer())
    await resp_cache.get_or_generate("q1", "s1", ["doc1"], 0, generate_fn)
    await resp_cache.get_or_generate("q2", "s1", ["doc1"], 0, generate_fn)
    assert generate_fn.call_count == 2


async def test_response_cache_stats_available(resp_cache):
    stats = await resp_cache.get_stats()
    assert isinstance(stats, dict)
