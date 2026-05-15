from __future__ import annotations

from pathlib import Path

import pytest

from sonya.harness.approval import ApprovalManager, ApprovalStatus
from sonya.selfmod import ProposalStatus, ProposalStore
from sonya.selfmod.governed_change import GovernedChangeProtocol
from sonya.state import Substrate


@pytest.fixture()
def substrate(tmp_path: Path):
    sub = Substrate.open(tmp_path / "s.db")
    yield sub
    sub.close()


def test_request_creates_approval(substrate: Substrate) -> None:
    store = ProposalStore(substrate)
    approvals = ApprovalManager(substrate)
    protocol = GovernedChangeProtocol(store, approvals)

    p = store.create(
        target_module="sonya.state.identity",
        change_summary="Modify things_not_to_betray",
        proposed_by_principal_id="sonya",
    )
    req = protocol.request_governed_change(p)
    assert req.status is ApprovalStatus.PENDING
    assert p.proposal_id in req.action


def test_non_anchor_approval_not_accepted(substrate: Substrate) -> None:
    store = ProposalStore(substrate)
    approvals = ApprovalManager(substrate)
    protocol = GovernedChangeProtocol(store, approvals, primary_anchor_principal_id="ivan")

    p = store.create(target_module="x", change_summary="y", proposed_by_principal_id="sonya")
    req = protocol.request_governed_change(p)
    approvals.approve(req.request_id, by_principal_id="random_user")

    result = protocol.check_governed_approval(p)
    assert result is False  # random_user is not ivan


def test_anchor_approval_accepted(substrate: Substrate) -> None:
    store = ProposalStore(substrate)
    approvals = ApprovalManager(substrate)
    protocol = GovernedChangeProtocol(store, approvals, primary_anchor_principal_id="ivan")

    p = store.create(target_module="x", change_summary="y", proposed_by_principal_id="sonya")
    req = protocol.request_governed_change(p)
    approvals.approve(req.request_id, by_principal_id="ivan")

    result = protocol.check_governed_approval(p)
    assert result is True
    loaded = store.get(p.proposal_id)
    assert loaded.status is ProposalStatus.GOVERNED_APPROVED


def test_pending_approval_returns_false(substrate: Substrate) -> None:
    store = ProposalStore(substrate)
    approvals = ApprovalManager(substrate)
    protocol = GovernedChangeProtocol(store, approvals)

    p = store.create(target_module="x", change_summary="y")
    protocol.request_governed_change(p)

    result = protocol.check_governed_approval(p)
    assert result is False
