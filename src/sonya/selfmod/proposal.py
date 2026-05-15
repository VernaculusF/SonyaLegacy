from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from sonya.state.substrate import Substrate


class ProposalStatus(str, Enum):
    DRAFT = "draft"
    VALIDATING = "validating"
    PASSED_LAYER_1 = "passed_layer_1"
    PASSED_LAYER_2 = "passed_layer_2"
    PASSED_LAYER_3 = "passed_layer_3"
    PASSED_LAYER_4 = "passed_layer_4"
    REQUIRES_GOVERNED_CHANGE = "requires_governed_change"
    GOVERNED_APPROVED = "governed_approved"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"
    REVERTED = "reverted"


class ProposalNotFoundError(KeyError):
    pass


@dataclass(frozen=True, slots=True)
class SelfModificationProposal:
    """A discrete proposal to modify Sonya's code/config/skills.

    Proposals go through the 4-layer validation pipeline (SUBSTRATE_STANCE §9).
    If Layer 4 (Anchor Integrity Check) flags identity-critical impact,
    the proposal requires governed change protocol with primary anchor approval.

    On MVP: proposals are stored and validated but NOT applied to filesystem.
    Real patching — post-MVP Track B.
    """

    proposal_id: str
    target_module: str
    change_summary: str
    diff_blob: str = ""
    proposed_by_principal_id: str | None = None
    status: ProposalStatus = ProposalStatus.DRAFT
    created_at: str = ""
    updated_at: str = ""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ProposalStore:
    """Persistent CRUD for SelfModificationProposal in substrate."""

    def __init__(self, substrate: Substrate) -> None:
        self._sub = substrate

    def create(
        self,
        *,
        target_module: str,
        change_summary: str,
        diff_blob: str = "",
        proposed_by_principal_id: str | None = None,
    ) -> SelfModificationProposal:
        proposal_id = f"smod-{uuid4().hex}"
        now = _utc_now_iso()
        self._sub.connection.execute(
            "INSERT INTO self_mod_proposals"
            "(proposal_id, target_module, change_summary, diff_blob, "
            "proposed_by_principal_id, status, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, 'draft', ?, ?)",
            (proposal_id, target_module, change_summary, diff_blob,
             proposed_by_principal_id, now, now),
        )
        self._sub.connection.commit()
        return SelfModificationProposal(
            proposal_id=proposal_id,
            target_module=target_module,
            change_summary=change_summary,
            diff_blob=diff_blob,
            proposed_by_principal_id=proposed_by_principal_id,
            status=ProposalStatus.DRAFT,
            created_at=now,
            updated_at=now,
        )

    def get(self, proposal_id: str) -> SelfModificationProposal:
        row = self._sub.connection.execute(
            "SELECT proposal_id, target_module, change_summary, diff_blob, "
            "proposed_by_principal_id, status, created_at, updated_at "
            "FROM self_mod_proposals WHERE proposal_id = ?",
            (proposal_id,),
        ).fetchone()
        if row is None:
            raise ProposalNotFoundError(proposal_id)
        return _row_to_proposal(row)

    def update_status(self, proposal_id: str, new_status: ProposalStatus) -> SelfModificationProposal:
        now = _utc_now_iso()
        self._sub.connection.execute(
            "UPDATE self_mod_proposals SET status = ?, updated_at = ? WHERE proposal_id = ?",
            (new_status.value, now, proposal_id),
        )
        self._sub.connection.commit()
        return self.get(proposal_id)

    def list_by_status(self, status: ProposalStatus) -> list[SelfModificationProposal]:
        cursor = self._sub.connection.execute(
            "SELECT proposal_id, target_module, change_summary, diff_blob, "
            "proposed_by_principal_id, status, created_at, updated_at "
            "FROM self_mod_proposals WHERE status = ? ORDER BY created_at ASC",
            (status.value,),
        )
        return [_row_to_proposal(row) for row in cursor.fetchall()]

    def record_validation(
        self, proposal_id: str, layer: int, passed: bool, reason: str = ""
    ) -> None:
        now = _utc_now_iso()
        self._sub.connection.execute(
            "INSERT INTO self_mod_validation_results"
            "(proposal_id, layer, passed, reason, checked_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (proposal_id, layer, 1 if passed else 0, reason, now),
        )
        self._sub.connection.commit()


def _row_to_proposal(row) -> SelfModificationProposal:
    return SelfModificationProposal(
        proposal_id=row[0],
        target_module=row[1],
        change_summary=row[2],
        diff_blob=row[3],
        proposed_by_principal_id=row[4],
        status=ProposalStatus(row[5]),
        created_at=row[6],
        updated_at=row[7],
    )
