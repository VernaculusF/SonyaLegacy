"""Memory tools — semantic recall over episodic events.

Exposes:
    memory.recall <query>           — text-semantic recall (top-K cosine)
    memory.recall_visual <path>     — visual recall by perceptual hash
    memory.index_status             — diagnostic
"""

from __future__ import annotations

from sonya.memory.embedder import Embedder
from sonya.memory.recall import RecallStore
from sonya.state.substrate import Substrate


def _phash_hex_to_int(h: str) -> int | None:
    """Decode a phash hex string to integer for hamming distance.

    imagehash uses 64-bit phashes by default — 16 hex digits.
    Returns None on parse failure.
    """
    if not h:
        return None
    try:
        return int(h, 16)
    except (TypeError, ValueError):
        return None


def _hamming_distance(a: int, b: int) -> int:
    """Number of bit positions where a and b differ."""
    return (a ^ b).bit_count()


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

    def recall_visual(self, media_path: str, top_k: int = 5,
                      max_distance: int = 12) -> str:
        """Find episodic events with perceptually-similar images.

        Computes pHash of `media_path`, then finds events whose stored
        ``media_phash`` is within ``max_distance`` bits (Hamming distance).

        Cheap — no embeddings, just bit comparison over rows that have
        a phash. Default ``max_distance=12`` is the standard pHash
        threshold for "looks the same to a human".

        Returns top-K sorted by ascending distance (most similar first).
        """
        path = (media_path or "").strip()
        if not path:
            return "[ERROR] memory.recall_visual needs a media path"
        try:
            from sonya.planning.memory_wiring import _compute_phash
            target_hex = _compute_phash(path)
        except Exception as exc:
            return f"[ERROR] phash compute failed: {exc}"
        if not target_hex:
            return (
                "[ERROR] could not compute phash — file unreadable or "
                "not a supported image format (need PIL + imagehash)"
            )
        target_int = _phash_hex_to_int(target_hex)
        if target_int is None:
            return f"[ERROR] phash decode failed for hex: {target_hex!r}"

        try:
            rows = self._sub.connection.execute(
                "SELECT event_id, event_type, raw_content, normalized_summary, "
                "media_phash, timestamp, channel "
                "FROM episodic_events "
                "WHERE media_phash IS NOT NULL AND media_phash != '' "
                "ORDER BY rowid DESC"
            ).fetchall()
        except Exception as exc:
            return f"[ERROR] episodic scan failed: {exc}"

        scored: list[tuple[int, dict]] = []
        for r in rows:
            evt_id, evt_type, raw, norm, ph_hex, ts, chan = r
            cand = _phash_hex_to_int(ph_hex)
            if cand is None:
                continue
            dist = _hamming_distance(target_int, cand)
            if dist > max_distance:
                continue
            scored.append((dist, {
                "event_id": evt_id,
                "event_type": evt_type,
                "raw_content": raw or "",
                "normalized_summary": norm or "",
                "phash": ph_hex,
                "timestamp": ts,
                "channel": chan or "",
                "distance": dist,
            }))

        if not scored:
            return (
                f"No similar images found (target phash {target_hex}). "
                f"Searched {len(rows)} events with phash. "
                f"Tip: max_distance={max_distance}; raise it if you expect "
                f"different crops / formats."
            )

        scored.sort(key=lambda t: t[0])
        top = scored[:top_k]
        lines = [
            f"Found {len(scored)} similar images (target phash {target_hex}). "
            f"Top {len(top)}:"
        ]
        for dist, ev in top:
            preview = (ev["normalized_summary"] or ev["raw_content"]
                       ).replace("\n", " ")[:160]
            lines.append(
                f"[d={dist:>2}] [{ev['event_type']} {ev['timestamp'][:16]} "
                f"{ev['channel']}] {preview}"
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
