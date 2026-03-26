"""Tests for MemoryManager, ContextBuilder, and MemoryCompressor."""
from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.config import Settings
from app.db.session_store import SessionStore
from app.memory.context_builder import ContextBuilder
from app.memory.memory_compressor import MemoryCompressor
from app.memory.memory_manager import MemoryManager
from app.models.query import Citation
from app.models.session import ConversationTurn


def _turn(user_q: str = "Q", assistant: str = "A", is_summary: bool = False,
          summary_text: str | None = None) -> ConversationTurn:
    return ConversationTurn(
        user_query=user_q,
        standalone_query=user_q,
        assistant_response=assistant,
        retrieved_chunk_ids=[str(uuid.uuid4())],
        is_summary=is_summary,
        summary_text=summary_text,
    )


# ===========================================================================
# ContextBuilder
# ===========================================================================

@pytest.fixture
def builder() -> ContextBuilder:
    return ContextBuilder()


def test_build_empty_turns_returns_empty_string(builder):
    assert builder.build([]) == ""


def test_build_single_turn(builder):
    turn = _turn("What is AI?", "AI stands for artificial intelligence.")
    result = builder.build([turn], token_budget=2000)
    assert "What is AI?" in result
    assert "AI stands for artificial intelligence." in result


def test_build_multiple_turns_chronological_order(builder):
    turns = [_turn(f"Q{i}", f"A{i}") for i in range(3)]
    result = builder.build(turns, token_budget=2000)
    # Q0 should appear before Q2 in the output
    assert result.index("Q0") < result.index("Q2")


def test_build_token_budget_respected(builder):
    # Create many turns that exceed any small budget
    turns = [_turn("What " * 50, "Answer " * 50) for _ in range(10)]
    result = builder.build(turns, token_budget=50)
    # The result should be significantly shorter than the full history
    from app.utils.token_counter import count_tokens
    assert count_tokens(result) <= 100  # some slack for formatting


def test_build_newest_turns_prioritised_when_trimming(builder):
    turns = [_turn(f"Old question {i}", f"Old answer {i}") for i in range(5)]
    turns.append(_turn("Very recent question", "Very recent answer"))
    result = builder.build(turns, token_budget=80)
    # The most recent turn should be in the output
    assert "Very recent question" in result


def test_build_summary_turn_rendered_with_prefix(builder):
    summary_turn = _turn(is_summary=True, summary_text="Previously: user asked about AI.")
    result = builder.build([summary_turn], token_budget=2000)
    assert "Summary of earlier conversation:" in result
    assert "Previously: user asked about AI." in result


def test_estimate_tokens_non_zero(builder):
    turns = [_turn("Hello", "World")]
    assert builder.estimate_tokens(turns) > 0


# ===========================================================================
# MemoryManager
# ===========================================================================

@pytest.fixture
def compressor_mock() -> MemoryCompressor:
    mock = AsyncMock(spec=MemoryCompressor)
    mock.should_compress = MagicMock(return_value=False)
    mock.compress = AsyncMock(side_effect=lambda turns, **kw: turns)
    return mock


@pytest.fixture
def memory_manager(session_store, compressor_mock) -> MemoryManager:
    return MemoryManager(
        session_store=session_store,
        context_builder=ContextBuilder(),
        compressor=compressor_mock,
    )


async def test_get_formatted_history_empty_session(memory_manager, sample_session):
    result = await memory_manager.get_formatted_history(sample_session.session_id)
    assert result == ""


async def test_record_turn_increases_turn_count(memory_manager, sample_session,
                                                  session_store):
    await memory_manager.record_turn(
        session_id=sample_session.session_id,
        user_query="What is ML?",
        standalone_query="What is machine learning?",
        assistant_response="ML is a subset of AI.",
        retrieved_chunk_ids=["chunk-1"],
        citations=[],
    )
    updated = await session_store.get_session(sample_session.session_id)
    assert updated.turn_count == 1


async def test_record_turn_stores_all_fields(memory_manager, sample_session,
                                               session_store):
    await memory_manager.record_turn(
        session_id=sample_session.session_id,
        user_query="Original Q",
        standalone_query="Standalone Q",
        assistant_response="The answer.",
        retrieved_chunk_ids=["c1", "c2"],
        citations=[],
    )
    session = await session_store.get_session(sample_session.session_id)
    turn = session.conversation_history[0]
    assert turn.user_query == "Original Q"
    assert turn.standalone_query == "Standalone Q"
    assert turn.assistant_response == "The answer."
    assert turn.retrieved_chunk_ids == ["c1", "c2"]


async def test_get_formatted_history_after_record_turn(memory_manager, sample_session):
    await memory_manager.record_turn(
        session_id=sample_session.session_id,
        user_query="Hello",
        standalone_query="Hello",
        assistant_response="Hi there.",
        retrieved_chunk_ids=[],
        citations=[],
    )
    history = await memory_manager.get_formatted_history(
        sample_session.session_id, token_budget=1024
    )
    assert "Hello" in history
    assert "Hi there." in history


async def test_get_turn_count_zero_for_new_session(memory_manager, sample_session):
    count = await memory_manager.get_turn_count(sample_session.session_id)
    assert count == 0


async def test_get_turn_count_after_record(memory_manager, sample_session):
    for i in range(3):
        await memory_manager.record_turn(
            session_id=sample_session.session_id,
            user_query=f"Q{i}",
            standalone_query=f"Q{i}",
            assistant_response=f"A{i}",
            retrieved_chunk_ids=[],
            citations=[],
        )
    count = await memory_manager.get_turn_count(sample_session.session_id)
    assert count == 3


# ===========================================================================
# Compression
# ===========================================================================

async def test_compression_triggered_at_threshold(session_store, settings):
    """When turn_count >= threshold, compressor.compress() is called."""
    compressor = AsyncMock(spec=MemoryCompressor)
    # Threshold = 2 for this test
    compressor.should_compress = MagicMock(side_effect=lambda n: n >= 2)
    compressed_turns = [_turn("summary", is_summary=True, summary_text="Summary text")]
    compressor.compress = AsyncMock(return_value=compressed_turns)

    manager = MemoryManager(session_store, ContextBuilder(), compressor)
    session = await session_store.create_session(["doc-1"])

    for i in range(2):
        await manager.record_turn(
            session_id=session.session_id,
            user_query=f"Q{i}",
            standalone_query=f"Q{i}",
            assistant_response=f"A{i}",
            retrieved_chunk_ids=[],
            citations=[],
        )

    compressor.compress.assert_called()


async def test_compression_not_triggered_below_threshold(session_store):
    compressor = AsyncMock(spec=MemoryCompressor)
    compressor.should_compress = MagicMock(return_value=False)
    compressor.compress = AsyncMock()

    manager = MemoryManager(session_store, ContextBuilder(), compressor)
    session = await session_store.create_session(["doc-1"])

    await manager.record_turn(
        session_id=session.session_id,
        user_query="Q",
        standalone_query="Q",
        assistant_response="A",
        retrieved_chunk_ids=[],
        citations=[],
    )

    compressor.compress.assert_not_called()
