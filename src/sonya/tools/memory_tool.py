"""Memory tools — semantic recall over episodic events.

Exposes `memory.recall <query>` and `memory.index_status` to the agent.
"""

from __future__ import annotations

from sonya.memory.embedder import Embedder
from sonya.memory.recall import RecallStore
from sonya.state.substrate import Substrate


class MemoryTool:
    """Agent-facing wrapper around RecallStore."""

    def __init__(self, substrate: Substrate) -> None:
        self._sub = substrate
        # Don't initialise embedder eagerly — first call pays the model load cost
        self._store: RecallStore | None = None

    def _get_store(self) -> RecallStore | None:
        if self._store is not None:
            return self._store
        if not Embedder.is_available():
            return None
        self._store = RecallStore(self._sub)
        return self._store

    def recall(self, query: str, top_k: int = 5) -> str:
        if not query.strip():
            return "[ERROR] memory.recall needs a query"
        store = self._get_store()
        if store is None:
            return (
                "[ERROR] embedder not available (fastembed not installed). "
                "Use self_inspect.memories for recency-only recall."
            )
        try:
            hits = store.recall(query.strip(), top_k=top_k)
        except Exception as exc:
            return f"[ERROR] recall failed: {exc}"
        if not hits:
            return f"No relevant memories found for: {query!r}"
        lines = [f"Top {len(hits)} memories for: {query!r}"]
        for h in hits:
            preview = h.raw_content.replace("\n", " ")[:200]
            lines.append(
                f"[{h.score:.2f}] [{h.event_type} {h.timestamp[:16]}] {preview}"
            )
        return "\n".join(lines)

    def index_status(self) -> str:
        store = self._get_store()
        if store is None:
            return "embedder unavailable (fastembed not installed)"
        indexed = store.count_indexed()
        pending = store.count_pending()
        return f"indexed={indexed} pending={pending}"


__all__ = ["MemoryTool"]
