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
    See: ANCHORS_AND_FAILURE_MODES §9.
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
    or constraint weakening. See ANCHORS_AND_FAILURE_MODES §9.
    """

    def __init__(self, stream: ContinuityStream) -> None:
        self._stream = stream

    def scan_recent(self, since_seq: int = 0) -> list[AnchorDriftSignal]:
        """Scan continuity events for drift indicators."""
        signals: list[AnchorDriftSignal] = []
        # Exclude detector self-output: drift_signal events contain the very
        # keywords we look for ('things_not_to_betray', etc.) in their payload
        # — without this filter the detector triggers on itself every tick.
        _SELF_KINDS = {
            "internal.drift_signal",
            "internal.capability_gap",
        }
        for event in self._stream.read_since(since_seq):
            if event.kind in _SELF_KINDS:
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
