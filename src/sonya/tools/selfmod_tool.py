"""Self-modification tool surface for Sonya.

Exposes the 4-layer self-modification pipeline as agent-callable tools.
This is the primary mechanism by which Sonya extends her own system.

Flow:
  1. Sonya writes proposed change as a diff (or new-file content)
  2. `selfmod.propose` records it as a SelfModificationProposal in substrate
  3. `selfmod.validate` runs Layers 1-4
     - Layer 1 (static_contract): syntax/imports/contract preserved
     - Layer 2 (behavioral_test): existing tests still pass on the change
     - Layer 3 (trace_replay): canonical traces produce same outcome
     - Layer 4 (anchor_integrity): doesn't touch identity-critical zones
  4. If APPROVED -> `selfmod.apply` writes to disk
  5. If REQUIRES_GOVERNED_CHANGE -> Ivan must approve via admin
  6. If REJECTED -> can amend & re-propose

See: docs/SYSTEM_BUILDOUT_PLAN.md Этап A, SUBSTRATE_STANCE §9.
"""

from __future__ import annotations

import json
from pathlib import Path

from sonya.harness.approval import ApprovalManager
from sonya.harness.audit import AuditLog
from sonya.selfmod import (
    GovernedChangeProtocol,
    Pipeline,
    ProposalStatus,
    ProposalStore,
    SelfModificationProposal,
    WatchWindow,
)
from sonya.selfmod.proposal import ProposalNotFoundError
from sonya.state.continuity_stream import ContinuityEvent, ContinuityStream
from sonya.state.substrate import Substrate


# Subpaths inside src/sonya/ that selfmod is allowed to modify.
# Outside of these — the proposal will fail Layer 4 even before anchor check.
SELFMOD_WRITABLE_SUBPATHS: tuple[str, ...] = (
    "src/sonya/channels",
    "src/sonya/tools",
    "src/sonya/skills",
    "src/sonya/planning",
    "src/sonya/initiative",
    "src/sonya/memory",
    "src/sonya/anchor",
    "src/sonya/embodiment",
    "src/sonya/simulation",
    "src/sonya/admin",
    "src/sonya/tasks",
    "src/sonya/subject",
    "src/sonya/runtime",
    "src/sonya/providers",
    "src/sonya/harness",
    "src/sonya/main.py",
    "src/sonya/config.py",
    "src/sonya/logging.py",
    "tests/sonya",
)

# Hard forbidden — even via selfmod pipeline.
SELFMOD_FORBIDDEN_SUBPATHS: tuple[str, ...] = (
    "src/sonya/state/seed.py",
    "src/sonya/state/schema.sql",
    "src/sonya/state/identity.py",
    "src/sonya/selfmod/layers/anchor_integrity.py",
    ".env",
    ".git",
    "tg.session",
    "docs/personality/SOUL.md",
    "docs/core",
)


class SelfModTool:
    """Agent-callable wrapper for the self-modification pipeline.

    Invoked from agent_session through `selfmod.*` tool calls.
    """

    def __init__(
        self,
        substrate: Substrate,
        project_root: Path | None = None,
        *,
        primary_anchor_principal_id: str = "ivan",
    ) -> None:
        self._sub = substrate
        self._root = (
            project_root or Path(__file__).resolve().parent.parent.parent.parent
        ).resolve()
        self._store = ProposalStore(substrate)
        self._stream = ContinuityStream(substrate)
        self._audit = AuditLog(substrate)
        self._approvals = ApprovalManager(substrate)
        self._pipeline = Pipeline(self._store, self._stream, self._audit)
        self._governed = GovernedChangeProtocol(
            self._store,
            self._approvals,
            primary_anchor_principal_id=primary_anchor_principal_id,
        )
        self._watchdog = WatchWindow(self._store, self._stream)

    # --- safety helpers ---

    def _check_target_writable(self, target_module: str) -> str | None:
        """Return error message if target_module is not writable via selfmod, else None."""
        # Normalize path separator
        target = target_module.replace("\\", "/").lstrip("/")

        # Forbidden first
        for forbidden in SELFMOD_FORBIDDEN_SUBPATHS:
            if target == forbidden or target.startswith(forbidden + "/"):
                return f"target_module '{target}' is in SELFMOD_FORBIDDEN_SUBPATHS"

        # Must match one of writable subpaths
        for allowed in SELFMOD_WRITABLE_SUBPATHS:
            if target == allowed or target.startswith(allowed + "/"):
                return None

        return (
            f"target_module '{target}' not in SELFMOD_WRITABLE_SUBPATHS. "
            f"Use plugins/ or workspace/ for unstructured changes."
        )

    # --- public tool methods ---

    def propose(
        self,
        target_module: str,
        change_summary: str,
        new_content: str = "",
        diff_blob: str = "",
        proposed_by: str | None = None,
    ) -> str:
        """Create a new SelfModificationProposal.

        target_module: relative path like 'src/sonya/channels/discord.py'
        change_summary: human-readable description
        new_content: full file content (for new files or full overwrite)
        diff_blob: alternative — unified diff string
        proposed_by: principal_id of proposer (defaults to 'sonya' for self-proposed)

        Returns: result JSON
        """
        err = self._check_target_writable(target_module)
        if err:
            return json.dumps({"status": "rejected_pre_pipeline", "reason": err})

        if not new_content and not diff_blob:
            return json.dumps({
                "status": "error",
                "reason": "either new_content or diff_blob required",
            })

        # Use new_content as diff_blob if no diff provided
        # (Layer 1 will treat it as a full-file replacement when applied)
        blob = diff_blob or f"FULL_CONTENT:\n{new_content}"

        proposal = self._store.create(
            target_module=target_module,
            change_summary=change_summary,
            diff_blob=blob,
            proposed_by_principal_id=proposed_by or "sonya",
        )
        return json.dumps({
            "status": "created",
            "proposal_id": proposal.proposal_id,
            "target_module": proposal.target_module,
            "current_status": proposal.status.value,
        })

    def validate(self, proposal_id: str) -> str:
        """Run all 4 layers on a proposal. Returns layer-by-layer results."""
        try:
            proposal = self._store.get(proposal_id)
        except ProposalNotFoundError:
            return json.dumps({"status": "error", "reason": f"proposal {proposal_id} not found"})

        results = self._pipeline.validate(proposal)
        final = self._store.get(proposal_id)

        return json.dumps({
            "status": "validated",
            "proposal_id": proposal_id,
            "final_status": final.status.value,
            "layers": [
                {"layer": r.layer, "passed": r.passed, "reason": r.reason}
                for r in results
            ],
        })

    def apply(self, proposal_id: str) -> str:
        """Apply an APPROVED or GOVERNED_APPROVED proposal to disk.

        Writes target_module file with new content. Records apply event.
        """
        try:
            proposal = self._store.get(proposal_id)
        except ProposalNotFoundError:
            return json.dumps({"status": "error", "reason": f"proposal {proposal_id} not found"})

        if proposal.status not in (ProposalStatus.APPROVED, ProposalStatus.GOVERNED_APPROVED):
            return json.dumps({
                "status": "error",
                "reason": f"proposal status is {proposal.status.value}, must be approved or governed_approved",
            })

        # Re-check target writable (defense in depth)
        err = self._check_target_writable(proposal.target_module)
        if err:
            return json.dumps({"status": "error", "reason": err})

        # Extract content
        diff_blob = proposal.diff_blob
        if diff_blob.startswith("FULL_CONTENT:\n"):
            content = diff_blob[len("FULL_CONTENT:\n"):]
        else:
            return json.dumps({
                "status": "error",
                "reason": "only FULL_CONTENT proposals are applicable in MVP. Use new_content parameter.",
            })

        # Write to disk
        target_path = (self._root / proposal.target_module).resolve()
        try:
            target_path.relative_to(self._root)
        except ValueError:
            return json.dumps({"status": "error", "reason": "target outside project root"})

        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_text(content, encoding="utf-8")

        # Mark applied
        self._store.update_status(proposal_id, ProposalStatus.APPLIED)
        self._stream.append(ContinuityEvent(
            kind="self_mod.applied",
            payload={
                "proposal_id": proposal_id,
                "target_module": proposal.target_module,
                "summary": proposal.change_summary,
                "size": len(content),
            },
        ))
        self._audit.append(
            principal_id=proposal.proposed_by_principal_id,
            action="selfmod.apply",
            decision="applied",
            scope=f"selfmod.{proposal.target_module}",
            metadata={"proposal_id": proposal_id},
        )

        return json.dumps({
            "status": "applied",
            "proposal_id": proposal_id,
            "target_module": proposal.target_module,
            "bytes_written": len(content),
            "note": "process restart may be required for the change to take effect (hot-reload only works for tools/plugins/)",
        })

    def list_proposals(self, status_filter: str = "") -> str:
        """List proposals, optionally filtered by status.

        Status values: draft, validating, passed_layer_1, passed_layer_2,
        passed_layer_3, passed_layer_4, requires_governed_change,
        governed_approved, approved, rejected, applied, reverted.
        """
        if status_filter:
            try:
                status = ProposalStatus(status_filter.strip().lower())
            except ValueError:
                return json.dumps({
                    "status": "error",
                    "reason": f"unknown status: {status_filter}. Valid: {[s.value for s in ProposalStatus]}",
                })
            proposals = self._store.list_by_status(status)
        else:
            # List all by querying every status
            proposals = []
            for s in ProposalStatus:
                proposals.extend(self._store.list_by_status(s))
            proposals.sort(key=lambda p: p.created_at, reverse=True)
            proposals = proposals[:50]  # cap

        return json.dumps({
            "status": "ok",
            "count": len(proposals),
            "proposals": [
                {
                    "proposal_id": p.proposal_id,
                    "target_module": p.target_module,
                    "summary": p.change_summary[:100],
                    "status": p.status.value,
                    "created_at": p.created_at,
                }
                for p in proposals
            ],
        })

    def get_proposal(self, proposal_id: str) -> str:
        """Get full details of one proposal including diff_blob."""
        try:
            p = self._store.get(proposal_id)
        except ProposalNotFoundError:
            return json.dumps({"status": "error", "reason": f"proposal {proposal_id} not found"})

        return json.dumps({
            "status": "ok",
            "proposal_id": p.proposal_id,
            "target_module": p.target_module,
            "change_summary": p.change_summary,
            "diff_blob": p.diff_blob[:5000],  # cap
            "diff_blob_truncated": len(p.diff_blob) > 5000,
            "proposed_by": p.proposed_by_principal_id,
            "current_status": p.status.value,
            "created_at": p.created_at,
            "updated_at": p.updated_at,
        })

    def request_governed(self, proposal_id: str) -> str:
        """For REQUIRES_GOVERNED_CHANGE proposals — create approval request."""
        try:
            p = self._store.get(proposal_id)
        except ProposalNotFoundError:
            return json.dumps({"status": "error", "reason": f"proposal {proposal_id} not found"})

        if p.status != ProposalStatus.REQUIRES_GOVERNED_CHANGE:
            return json.dumps({
                "status": "error",
                "reason": f"proposal status is {p.status.value}, expected requires_governed_change",
            })

        req = self._governed.request_governed_change(p)
        return json.dumps({
            "status": "approval_requested",
            "proposal_id": proposal_id,
            "approval_request_id": req.request_id,
            "note": "waiting for primary anchor approval via admin panel",
        })

    def check_governed(self, proposal_id: str) -> str:
        """Check if a previously requested governed change has been approved."""
        try:
            p = self._store.get(proposal_id)
        except ProposalNotFoundError:
            return json.dumps({"status": "error", "reason": f"proposal {proposal_id} not found"})

        approved = self._governed.check_governed_approval(p)
        # Reload to see if status changed
        p_after = self._store.get(proposal_id)

        return json.dumps({
            "status": "checked",
            "proposal_id": proposal_id,
            "approved": approved,
            "current_status": p_after.status.value,
        })

    def rollback(self, proposal_id: str, reason: str = "") -> str:
        """Mark a proposal as REVERTED. Does not currently restore file content
        (that would require keeping pre-state — TODO for next iteration)."""
        try:
            p = self._store.get(proposal_id)
        except ProposalNotFoundError:
            return json.dumps({"status": "error", "reason": f"proposal {proposal_id} not found"})

        if p.status != ProposalStatus.APPLIED:
            return json.dumps({
                "status": "error",
                "reason": f"can only rollback APPLIED proposals (current: {p.status.value})",
            })

        self._watchdog.trigger_revert(p, reason=reason or "manual rollback")
        return json.dumps({
            "status": "reverted",
            "proposal_id": proposal_id,
            "note": "status marked REVERTED. File content NOT auto-restored (manual revert needed for now).",
        })
