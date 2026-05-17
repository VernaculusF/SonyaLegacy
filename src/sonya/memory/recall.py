"""Semantic recall over episodic memory.

Reads/writes the `embedding` BLOB column on `episodic_events`. Indexer fills
it for events that don't have one yet. Search loads all non-archived
embeddings into memory and computes cosine similarity via numpy — fast enough
for tens of thousands of rows on CPU (one matvec, AVX2-friendly).

Once volume exceeds ~100k events we'd switch to faiss/hnswlib, but that's a
separate problem.

`numpy` is imported lazily inside the methods so the module is safe to import
in environments without numpy/fastembed; the methods will raise
EmbedderUnavailableError if actually called there.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sonya.memory.embedder import (
    Embedder,
    blob_to_vector,
    vector_to_blob,
)
from sonya.state.substrate import Substrate


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class RecallHit:
    event_id: str
    event_type: str
    timestamp: str
    raw_content: str
    score: float


class RecallStore:
    """Embedding index over episodic_events.

    Designed for single-writer (the indexer in main.py) and many-reader
    (recall tool calls) usage; SQLite WAL handles concurrency.
    """

    def __init__(self, substrate: Substrate, embedder: Embedder | None = None) -> None:
        self._sub = substrate
        self._embedder = embedder or Embedder.shared()

    # ----- indexing -----

    def count_pending(self) -> int:
        """How many unarchived events still need an embedding."""
        cursor = self._sub.connection.execute(
            "SELECT COUNT(*) FROM episodic_events "
            "WHERE archived = 0 AND (embedding IS NULL OR embedded_at = '')"
        )
        return int(cursor.fetchone()[0])

    def count_indexed(self) -> int:
        cursor = self._sub.connection.execute(
            "SELECT COUNT(*) FROM episodic_events "
            "WHERE archived = 0 AND embedding IS NOT NULL AND embedded_at != ''"
        )
        return int(cursor.fetchone()[0])

    def fetch_pending_batch(self, batch_size: int = 256) -> list[tuple[str, str]]:
        """Return [(event_id, text), ...] for events that still need embeddings.

        text = raw_content if non-empty, else normalized_summary.
        Empty events are marked as embedded with a 0-byte blob to avoid loops.
        """
        cursor = self._sub.connection.execute(
            "SELECT event_id, raw_content, normalized_summary FROM episodic_events "
            "WHERE archived = 0 AND (embedding IS NULL OR embedded_at = '') "
            "ORDER BY timestamp DESC LIMIT ?",
            (batch_size,),
        )
        out: list[tuple[str, str]] = []
        for event_id, raw, summary in cursor.fetchall():
            text = (raw or "").strip() or (summary or "").strip()
            if not text:
                self._sub.connection.execute(
                    "UPDATE episodic_events SET embedding = ?, embedded_at = ? WHERE event_id = ?",
                    (b"", _utc_now_iso(), event_id),
                )
                continue
            out.append((event_id, text))
        self._sub.connection.commit()
        return out

    def index_batch(self, batch_size: int = 256) -> int:
        """Embed up to `batch_size` pending events. Returns how many were embedded."""
        pending = self.fetch_pending_batch(batch_size)
        if not pending:
            return 0
        ids = [row[0] for row in pending]
        texts = [row[1] for row in pending]
        vectors = self._embedder.encode(texts)
        now = _utc_now_iso()
        with self._sub.connection:
            for event_id, vec in zip(ids, vectors):
                self._sub.connection.execute(
                    "UPDATE episodic_events SET embedding = ?, embedded_at = ? "
                    "WHERE event_id = ?",
                    (vector_to_blob(vec), now, event_id),
                )
        return len(ids)

    # ----- recall -----

    def recall(self, query: str, top_k: int = 5, *, min_score: float = 0.25) -> list[RecallHit]:
        """Return top-k events most similar to `query`.

        Reads ALL indexed embeddings into memory and does one matmul. Fine up
        to ~100k rows. `min_score` filters away noise (cosine 0 — orthogonal,
        1 — identical).
        """
        if not query.strip():
            return []
        import numpy as np  # local — keep module import-safe without numpy

        cursor = self._sub.connection.execute(
            "SELECT event_id, event_type, timestamp, raw_content, embedding "
            "FROM episodic_events "
            "WHERE archived = 0 AND embedding IS NOT NULL AND length(embedding) > 0 "
            "ORDER BY timestamp DESC"
        )
        rows = cursor.fetchall()
        if not rows:
            return []
        ids: list[str] = []
        types: list[str] = []
        timestamps: list[str] = []
        contents: list[str] = []
        vecs = []
        for event_id, ev_type, ts, content, blob in rows:
            v = blob_to_vector(blob)
            if v.shape[0] != self._embedder.dim:
                continue  # corrupt / wrong-dim row, skip
            ids.append(event_id)
            types.append(ev_type)
            timestamps.append(ts)
            contents.append(content or "")
            vecs.append(v)
        if not vecs:
            return []
        matrix = np.stack(vecs, axis=0)  # (N, 384)
        q = self._embedder.encode_one(query)  # (384,)
        scores = matrix @ q  # (N,)
        order = np.argsort(-scores)[:top_k]
        hits: list[RecallHit] = []
        for idx in order:
            score = float(scores[idx])
            if score < min_score:
                break
            hits.append(RecallHit(
                event_id=ids[idx],
                event_type=types[idx],
                timestamp=timestamps[idx],
                raw_content=contents[idx],
                score=score,
            ))
        return hits


__all__ = ["RecallStore", "RecallHit"]
