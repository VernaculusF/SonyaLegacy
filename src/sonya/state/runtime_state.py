"""Technical process coordination state excluded from Sonya's world model."""

from __future__ import annotations

from datetime import datetime, timezone

from sonya.state.substrate import Substrate


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class RuntimeStateStore:
    def __init__(self, substrate: Substrate) -> None:
        self._sub = substrate

    def set(self, key: str, value: str) -> None:
        key = (key or "").strip()
        if not key:
            raise ValueError("runtime state key is required")
        self._sub.connection.execute(
            "INSERT INTO runtime_state(key, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, "
            "updated_at = excluded.updated_at",
            (key, value, _utc_now_iso()),
        )
        self._sub.connection.commit()

    def get(self, key: str) -> dict[str, str] | None:
        row = self._sub.connection.execute(
            "SELECT key, value, updated_at FROM runtime_state WHERE key = ?",
            (key,),
        ).fetchone()
        if row is None:
            return None
        return {"key": row[0], "value": row[1], "updated_at": row[2]}


__all__ = ["RuntimeStateStore"]
