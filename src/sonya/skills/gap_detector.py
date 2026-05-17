from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from sonya.selfmod.proposal import ProposalStore
from sonya.state.continuity_stream import ContinuityStream
from sonya.state.substrate import Substrate


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class CapabilityGap:
    """A detected missing capability.

    Created when the internal process notices a failed action pattern
    or an explicit "I cannot do X" in continuity events.
    """

    gap_id: str
    description: str
    detected_from_event_seq: int | None = None
    proposal_id: str | None = None
    status: str = "open"  # open, proposed, resolved
    created_at: str = ""


class GapDetector:
    """Detects capability gaps from recent continuity events.

    Looks for internal.cognitive_tick events with triggers containing
    failure patterns. Creates CapabilityGap objects in substrate and
    optionally bridges them to SelfModificationProposal.

    See: SKILL_SYSTEM_PLAN, SELF_REWRITE_STANCE §1.
    """

    # Keywords in continuity event payloads that signal a gap
    _GAP_SIGNALS: tuple[str, ...] = (
        "cannot",
        "no_skill",
        "missing_capability",
        "failed_action",
        "not_implemented",
    )

    def __init__(self, substrate: Substrate, stream: ContinuityStream) -> None:
        self._sub = substrate
        self._stream = stream

    def scan_recent(self, since_seq: int = 0) -> list[CapabilityGap]:
        """Scan continuity events since `since_seq` for gap signals."""
        gaps: list[CapabilityGap] = []
        # Exclude detector self-output and noisy event types whose payloads
        # are likely to contain the trigger words ('cannot', 'failed') as
        # legitimate text rather than capability gaps.
        # `internal.agent_session_outcome` — final agent summary often hedges
        # ('I cannot complete this in 8 steps' is not a capability gap, it's
        # a budget exhaustion).
        _SKIP_KINDS = {
            "internal.capability_gap",
            "internal.drift_signal",
            "internal.agent_step",
            "internal.agent_session_outcome",
            "internal.agent_session_complete",
            "incoming.telegram_message",
            "outgoing.response",
            "outgoing.telegram_response",
            "outgoing.telegram_initiative",
            "internal.thought",
            "internal.cognitive_tick",
        }
        for event in self._stream.read_since(since_seq):
            if event.kind in _SKIP_KINDS:
                continue
            if self._is_gap_signal(event.payload):
                gap = self._create_gap(
                    description=self._extract_description(event.payload),
                    event_seq=event.seq,
                )
                gaps.append(gap)
        return gaps

    def create_proposal_from_gap(
        self, gap: CapabilityGap, proposal_store: ProposalStore
    ) -> str:
        """Bridge a gap to a SelfModificationProposal. Returns proposal_id."""
        proposal = proposal_store.create(
            target_module="sonya.skills.registry",
            change_summary=f"Add skill to address gap: {gap.description}",
            proposed_by_principal_id="system.gap_detector",
        )
        # Update gap with proposal link
        self._sub.connection.execute(
            "UPDATE capability_gaps SET proposal_id = ?, status = 'proposed' WHERE gap_id = ?",
            (proposal.proposal_id, gap.gap_id),
        )
        self._sub.connection.commit()
        return proposal.proposal_id

    def _is_gap_signal(self, payload: dict) -> bool:
        text = str(payload).lower()
        return any(signal in text for signal in self._GAP_SIGNALS)

    def _extract_description(self, payload: dict) -> str:
        triggers = payload.get("triggers", [])
        if triggers:
            return f"Gap detected from triggers: {', '.join(str(t) for t in triggers)}"
        return f"Gap detected from payload: {str(payload)[:100]}"

    def _create_gap(self, description: str, event_seq: int | None = None) -> CapabilityGap:
        gap_id = f"gap-{uuid4().hex}"
        now = _utc_now_iso()
        self._sub.connection.execute(
            "INSERT INTO capability_gaps(gap_id, description, detected_from_event_seq, status, created_at) "
            "VALUES (?, ?, ?, 'open', ?)",
            (gap_id, description, event_seq, now),
        )
        self._sub.connection.commit()
        return CapabilityGap(
            gap_id=gap_id,
            description=description,
            detected_from_event_seq=event_seq,
            status="open",
            created_at=now,
        )
