"""Environment state — Sonya's observation of Ivan's context.

Substrate v15 table `environment_state`. Sonya writes here via env.set tool
when she infers something from conversation (e.g. Ivan said he's going to
sleep, going to work, busy with something). The values surface in the
context_builder so future LLM calls and the OutboundGate know whether to
initiate.

There are no clock heuristics. Sonya is the observer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sonya.state.substrate import Substrate


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EnvironmentStore:
    """CRUD over environment_state."""

    def __init__(self, substrate: Substrate) -> None:
        self._sub = substrate

    def set(
        self,
        key: str,
        value: str,
        *,
        source: str = "observation",
        updated_by: str = "",
    ) -> None:
        key = (key or "").strip()
        if not key:
            raise ValueError("environment key is required")
        now = _utc_now_iso()
        self._sub.connection.execute(
            "INSERT INTO environment_state(key, value, source, updated_at, updated_by) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET "
            "value = excluded.value, source = excluded.source, "
            "updated_at = excluded.updated_at, updated_by = excluded.updated_by",
            (key, value, source, now, updated_by),
        )
        self._sub.connection.commit()

    def get(self, key: str) -> dict[str, Any] | None:
        row = self._sub.connection.execute(
            "SELECT key, value, source, updated_at, updated_by "
            "FROM environment_state WHERE key = ?",
            (key,),
        ).fetchone()
        if row is None:
            return None
        return {
            "key": row[0],
            "value": row[1],
            "source": row[2],
            "updated_at": row[3],
            "updated_by": row[4],
        }

    def list_all(self) -> dict[str, dict[str, Any]]:
        cursor = self._sub.connection.execute(
            "SELECT key, value, source, updated_at, updated_by "
            "FROM environment_state ORDER BY key"
        )
        return {
            row[0]: {
                "value": row[1],
                "source": row[2],
                "updated_at": row[3],
                "updated_by": row[4],
            }
            for row in cursor.fetchall()
        }

    def clear(self, key: str) -> bool:
        cur = self._sub.connection.execute(
            "DELETE FROM environment_state WHERE key = ?", (key,)
        )
        self._sub.connection.commit()
        return cur.rowcount > 0


__all__ = ["EnvironmentStore"]
