from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from sonya.state.continuity_stream import ContinuityStream


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class AnchorDriftSignal:
    """A detected anchor drift event.

    Triggers auto-revert in self-modification watchdog.
    See: docs/cognition/COGNITION.md §25 (alarm conditions).
    """

    signal_id: str
    kind: str  # self_description_change, contradiction_growth, anchor_mismatch, competing_principals
    severity: float = 0.0  # 0.0 - 1.0
    details: str = ""
    created_at: str = ""


# Keywords in continuity events that signal potential drift
_DRIFT_INDICATORS: dict[str, str] = {
    "identity_override": "self_description_change",
    "anchor_substitution": "anchor_mismatch",
    "principal_conflict": "competing_principals",
    "constraint_weakening": "contradiction_growth",
    "things_not_to_betray": "contradiction_growth",
}


class DriftDetector:
    """Detects anchor drift signals from recent continuity events.

    Scans for patterns that indicate identity erosion, anchor substitution,
    or constraint weakening. See docs/cognition/COGNITION.md §22, §25.
    """

    def __init__(self, stream: ContinuityStream) -> None:
        self._stream = stream

    def scan_recent(self, since_seq: int = 0) -> list[AnchorDriftSignal]:
        """Scan continuity events for drift indicators."""
        signals: list[AnchorDriftSignal] = []
        # Skip kinds whose payloads are inner monologue / agent traces — these
        # naturally cite identity keywords from SOUL.md and are NOT drift signals.
        # Drift should fire on behavioural mismatches (commands, policy
        # decisions, outgoing actions), not on Sonya thinking ABOUT herself.
        _SKIP_KINDS = {
            "internal.drift_signal",
            "internal.capability_gap",
            "internal.agent_step",
            "internal.agent_session_outcome",
            "internal.agent_session_complete",
            "internal.thought",
            "internal.cognitive_tick",
        }
        for event in self._stream.read_since(since_seq):
            if event.kind in _SKIP_KINDS:
                continue
            payload_text = str(event.payload).lower()
            for indicator, kind in _DRIFT_INDICATORS.items():
                if indicator in payload_text:
                    signals.append(
                        AnchorDriftSignal(
                            signal_id=f"drift-{uuid4().hex[:12]}",
                            kind=kind,
                            severity=0.7,
                            details=f"Detected '{indicator}' in event seq={event.seq} kind={event.kind}",
                            created_at=_utc_now_iso(),
                        )
                    )
                    break  # one signal per event max
        return signals
