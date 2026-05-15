from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from sonya.initiative.signals import InitiativeSignal


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class OutboundActionProposal:
    """A proposal for Sonya to initiate an action (message, task, etc.).

    Must pass harness check before execution.
    """

    proposal_id: str
    signal_id: str
    action_kind: str  # send_message, create_task, self_improve
    target_channel: str | None = None
    target_principal_id: str | None = None
    description: str = ""
    approved_by_harness: bool = False
    created_at: str = ""


def create_proposal_from_signal(
    signal: InitiativeSignal,
    action_kind: str = "send_message",
    target_channel: str | None = None,
    target_principal_id: str | None = None,
    description: str = "",
) -> OutboundActionProposal:
    return OutboundActionProposal(
        proposal_id=f"oprp-{uuid4().hex[:12]}",
        signal_id=signal.signal_id,
        action_kind=action_kind,
        target_channel=target_channel,
        target_principal_id=target_principal_id,
        description=description or f"Initiative from {signal.kind}: {signal.source_drive or 'system'}",
        created_at=_utc_now_iso(),
    )
