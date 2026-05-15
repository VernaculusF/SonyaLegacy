from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class InitiativeSignal:
    """An internal signal that may trigger an outbound action proposal."""

    signal_id: str
    kind: str  # drive_threshold_hit, deadline_approaching, gap_detected, drift_detected
    source_drive: str | None = None
    priority: int = 0  # higher = more urgent
    triggers_action_proposal: bool = True
    created_at: str = ""


def create_signal(
    kind: str,
    source_drive: str | None = None,
    priority: int = 0,
    triggers_action_proposal: bool = True,
) -> InitiativeSignal:
    return InitiativeSignal(
        signal_id=f"sig-{uuid4().hex[:12]}",
        kind=kind,
        source_drive=source_drive,
        priority=priority,
        triggers_action_proposal=triggers_action_proposal,
        created_at=_utc_now_iso(),
    )
