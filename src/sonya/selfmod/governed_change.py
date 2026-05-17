from __future__ import annotations

from sonya.harness.approval import ApprovalManager, ApprovalRequest, ApprovalStatus
from sonya.selfmod.proposal import ProposalStatus, ProposalStore, SelfModificationProposal


class GovernedChangeProtocol:
    """Governed change protocol for identity-critical self-modifications.

    When Layer 4 (Anchor Integrity Check) flags a proposal as identity-critical,
    it requires explicit approval from the primary anchor (Ivan) before proceeding.

    See: SUBSTRATE_STANCE §9.4, §11.
    """

    def __init__(
        self,
        proposal_store: ProposalStore,
        approval_manager: ApprovalManager,
        *,
        primary_anchor_principal_id: str = "ivan",
    ) -> None:
        self._proposals = proposal_store
        self._approvals = approval_manager
        self._anchor_id = primary_anchor_principal_id

    def request_governed_change(
        self, proposal: SelfModificationProposal
    ) -> ApprovalRequest:
        """Create an approval request for an identity-critical proposal."""
        return self._approvals.create(
            principal_id=proposal.proposed_by_principal_id or "system",
            action=f"selfmod.governed_change:{proposal.proposal_id}",
            scope=f"selfmod.{proposal.target_module}",
        )

    def check_governed_approval(
        self, proposal: SelfModificationProposal
    ) -> bool:
        """Check if the governed change has been approved by primary anchor.

        Returns True only if an approval exists for this proposal AND
        the approver is the primary anchor.
        """
        # Find all approval requests for this specific proposal_id via public API
        requests = self._approvals.find_by_action_pattern(
            f"%{proposal.proposal_id}%"
        )
        if not requests:
            return False

        for req in requests:
            if req.status is ApprovalStatus.PENDING:
                return False  # still waiting on a decision
            if (
                req.status is ApprovalStatus.APPROVED
                and req.decided_by_principal_id == self._anchor_id
            ):
                self._proposals.update_status(
                    proposal.proposal_id, ProposalStatus.GOVERNED_APPROVED
                )
                return True

        return False
