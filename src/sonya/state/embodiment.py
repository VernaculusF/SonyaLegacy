from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sonya.state.substrate import Substrate


@dataclass(frozen=True, slots=True)
class EmbodimentState:
    """Current physical/subjective state of the agent's embodiment."""

    outfit: str = "home"
    expression: str = "neutral"
    focus: str = "internal"
    mood_tint: str = "neutral"


class EmbodimentStore:
    """Authoritative store for embodiment state, backed by subject_state table."""

    def __init__(self, substrate: Substrate) -> None:
        self._sub = substrate

    def load(self) -> EmbodimentState:
        row = self._sub.connection.execute(
            "SELECT current_outfit, current_expression, current_focus, mood_tint "
            "FROM subject_state WHERE id = 1"
        ).fetchone()
        if row is None:
            return EmbodimentState()
        return EmbodimentState(
            outfit=row[0] or "home",
            expression=row[1] or "neutral",
            focus=row[2] or "internal",
            mood_tint=row[3] or "neutral",
        )

    def _update_column(self, col: str, val: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._sub.connection.execute(
            f"INSERT INTO subject_state(id, {col}, updated_at) VALUES (1, ?, ?) "
            f"ON CONFLICT(id) DO UPDATE SET {col} = excluded.{col}, updated_at = excluded.updated_at",
            (val, now),
        )
        self._sub.connection.commit()

    def set_outfit(self, outfit: str) -> None:
        self._update_column("current_outfit", outfit)

    def set_expression(self, expression: str) -> None:
        self._update_column("current_expression", expression)

    def set_mood_tint(self, tint: str) -> None:
        self._update_column("mood_tint", tint)

    def set_focus(self, focus: str) -> None:
        self._update_column("current_focus", focus)
