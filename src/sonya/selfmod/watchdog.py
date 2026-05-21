from __future__ import annotations

from sonya.selfmod.proposal import ProposalStatus, ProposalStore, SelfModificationProposal
from sonya.state.continuity_stream import ContinuityEvent, ContinuityStream


class WatchWindow:
    """Post-apply monitoring stub.

    After a proposal is applied, watches for anchor drift signals during
    a configurable window. If drift detected → auto-revert.

    STUB on MVP: drift signal is always False. Real anchor drift signals
    come in Phase 6 (Initiative Layer & Anchor Drift Signals).

    See: SUBSTRATE_STANCE §9.5.
    """

    def __init__(
        self,
        proposal_store: ProposalStore,
        stream: ContinuityStream,
        *,
        watch_hours: int = 24,
    ) -> None:
        self._store = proposal_store
        self._stream = stream
        self._watch_hours = watch_hours

    def confirm_stable(self, proposal: SelfModificationProposal) -> None:
        """Mark proposal as confirmed stable after watch window passes."""
        self._store.update_status(proposal.proposal_id, ProposalStatus.APPLIED)
        self._stream.append(
            ContinuityEvent(
                kind="self_mod.confirmed_stable",
                payload={"proposal_id": proposal.proposal_id},
            )
        )
        # Record baseline for 7-day outcome tracking
        try:
            from sonya.selfmod.outcome import record_baseline
            record_baseline(
                self._store._sub,
                proposal.proposal_id,
                proposal.target_module,
            )
        except Exception:
            pass

    def trigger_revert(self, proposal: SelfModificationProposal, reason: str = "") -> None:
        """Auto-revert a proposal due to drift signal."""
        self._store.update_status(proposal.proposal_id, ProposalStatus.REVERTED)
        self._stream.append(
            ContinuityEvent(
                kind="self_mod.auto_reverted",
                payload={
                    "proposal_id": proposal.proposal_id,
                    "reason": reason,
                },
            )
        )

    def check_drift_signal(self, proposal: SelfModificationProposal) -> bool:
        """Check if anchor drift signal fired for this proposal.

        STUB: always returns False. Real implementation in Phase 6.
        """
        return False
