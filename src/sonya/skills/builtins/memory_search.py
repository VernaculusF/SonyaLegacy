"""Skill: memory-search — semantic recall over episodic memory.

Triggered when Sonya needs to remember something specific. Wraps
memory.recall with context-aware query construction.
"""

from __future__ import annotations

from typing import Any


SKILL_ID = "skill-memory-search"
SKILL_NAME = "memory-search"
SKILL_PURPOSE = "Semantic recall: find relevant past events by meaning, not just recency."


def run(context: dict[str, Any]) -> str:
    """Execute the skill. Returns observation string."""
    substrate = context.get("substrate")
    query = context.get("query") or context.get("user_input") or ""
    top_k = int(context.get("top_k", 5))

    if not query.strip():
        return "(no query provided for memory-search)"

    if substrate is None:
        return "[ERROR] no substrate in context"

    try:
        from sonya.memory.embedder import Embedder
        if not Embedder.is_available():
            return "[SKIP] embedder not available"
        from sonya.memory.recall import RecallStore
        store = RecallStore(substrate)
        hits = store.recall(query.strip(), top_k=top_k)
    except Exception as exc:
        return f"[ERROR] memory-search failed: {exc}"

    if not hits:
        return f"No relevant memories for: {query!r}"

    lines = [f"Memory search results for: {query!r}"]
    for h in hits:
        preview = h.raw_content.replace("\n", " ")[:200]
        lines.append(f"[{h.score:.2f}] [{h.event_type} {h.timestamp[:16]}] {preview}")
    return "\n".join(lines)
