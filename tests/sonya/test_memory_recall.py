"""Smoke tests for memory recall — works whether numpy/fastembed are
installed or not (graceful degradation)."""

from __future__ import annotations

from pathlib import Path

import pytest

from sonya.memory.embedder import Embedder
from sonya.memory.recall import RecallStore
from sonya.state.substrate import Substrate
from sonya.tools.memory_tool import MemoryTool


@pytest.fixture()
def substrate(tmp_path: Path):
    sub = Substrate.open(tmp_path / "s.db")
    yield sub
    sub.close()


def test_recall_store_constructs(substrate: Substrate) -> None:
    """RecallStore can be created even without fastembed/numpy installed."""
    store = RecallStore(substrate)
    # No events yet — counts should be zero
    assert store.count_indexed() == 0
    assert store.count_pending() == 0


def test_memory_tool_handles_missing_embedder(substrate: Substrate) -> None:
    """MemoryTool returns a clear error string when fastembed isn't available."""
    tool = MemoryTool(substrate)
    out = tool.recall("test query")
    if Embedder.is_available():
        # With deps installed, expect either no-results or a top-N list.
        assert "memory" in out.lower() or "memories" in out.lower() or "no relevant" in out.lower()
    else:
        assert "embedder not available" in out.lower()


def test_memory_tool_rejects_empty_query(substrate: Substrate) -> None:
    tool = MemoryTool(substrate)
    out = tool.recall("")
    assert "[ERROR]" in out


def test_index_status(substrate: Substrate) -> None:
    tool = MemoryTool(substrate)
    out = tool.index_status()
    if Embedder.is_available():
        assert "indexed=" in out and "pending=" in out
    else:
        assert "unavailable" in out.lower()


@pytest.mark.skipif(not Embedder.is_available(), reason="fastembed/numpy not installed")
def test_recall_round_trip(substrate: Substrate) -> None:
    """End-to-end: write events, embed, recall by similarity."""
    from sonya.memory.episodic import EpisodicMemory

    mem = EpisodicMemory(substrate)
    mem.record(event_type="dialogue", raw_content="Иван рассказал про код Сони и память")
    mem.record(event_type="dialogue", raw_content="Готовлю ужин — суп и салат с курицей")
    mem.record(event_type="dialogue", raw_content="Думаю про эмбеддинги для поиска памяти")

    store = RecallStore(substrate)
    n = store.index_batch(batch_size=10)
    assert n == 3
    assert store.count_pending() == 0
    assert store.count_indexed() == 3

    hits = store.recall("семантический поиск памяти", top_k=2, min_score=0.0)
    assert hits, "expected at least one hit"
    # Top hit should be the embedding-related memory, not the cooking one
    assert "эмбеддинг" in hits[0].raw_content.lower() or "память" in hits[0].raw_content.lower()
