from __future__ import annotations

from sonya.selfmod.layers.static_contract import ValidationResult, check_static_contract
from sonya.selfmod.layers.behavioral_test import check_behavioral_test
from sonya.selfmod.layers.trace_replay import check_trace_replay
from sonya.selfmod.layers.anchor_integrity import check_anchor_integrity
from sonya.selfmod.proposal import (
    ProposalStatus,
    ProposalStore,
    SelfModificationProposal,
)
from sonya.state.continuity_stream import ContinuityEvent, ContinuityStream
from sonya.harness.audit import AuditLog


class Pipeline:
    """4-layer self-modification validation pipeline.

    Runs layers 1-4 in order. Stops on first failure (except Layer 4 which
    returns requires_governed_change instead of outright rejection).

    Each layer result is recorded in substrate (validation_results table),
    continuity stream, and audit log.

    See: SUBSTRATE_STANCE §9.
    """

    def __init__(
        self,
        proposal_store: ProposalStore,
        stream: ContinuityStream,
        audit: AuditLog,
    ) -> None:
        self._store = proposal_store
        self._stream = stream
        self._audit = audit

    def validate(self, proposal: SelfModificationProposal) -> list[ValidationResult]:
        """Run all 4 layers. Returns list of results."""
        self._store.update_status(proposal.proposal_id, ProposalStatus.VALIDATING)

        results: list[ValidationResult] = []
        layers = [
            (check_static_contract, ProposalStatus.PASSED_LAYER_1),
            (check_behavioral_test, ProposalStatus.PASSED_LAYER_2),
            (check_trace_replay, ProposalStatus.PASSED_LAYER_3),
            (check_anchor_integrity, ProposalStatus.PASSED_LAYER_4),
        ]

        for check_fn, pass_status in layers:
            result = check_fn(proposal)
            results.append(result)

            # Record in substrate
            self._store.record_validation(
                proposal.proposal_id,
                layer=result.layer,
                passed=result.passed,
                reason=result.reason,
            )

            # Record in continuity
            self._stream.append(
                ContinuityEvent(
                    kind=f"self_mod.validation_layer_{result.layer}",
                    payload={
                        "proposal_id": proposal.proposal_id,
                        "layer": result.layer,
                        "passed": result.passed,
                        "reason": result.reason,
                    },
                )
            )

            # Record in audit
            self._audit.append(
                principal_id=proposal.proposed_by_principal_id,
                action=f"selfmod.validate_layer_{result.layer}",
                decision="pass" if result.passed else "fail",
                scope=f"selfmod.{proposal.target_module}",
                metadata={
                    "proposal_id": proposal.proposal_id,
                    "reason": result.reason,
                },
            )

            if not result.passed:
                # Layer 4 failure = requires governed change, not outright rejection
                if result.layer == 4:
                    self._store.update_status(
                        proposal.proposal_id,
                        ProposalStatus.REQUIRES_GOVERNED_CHANGE,
                    )
                else:
                    self._store.update_status(
                        proposal.proposal_id, ProposalStatus.REJECTED
                    )
                break
            else:
                self._store.update_status(proposal.proposal_id, pass_status)

        # If all 4 passed, mark approved
        if all(r.passed for r in results) and len(results) == 4:
            self._store.update_status(proposal.proposal_id, ProposalStatus.APPROVED)

        return results
