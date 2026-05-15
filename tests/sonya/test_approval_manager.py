from __future__ import annotations

from pathlib import Path

import pytest

from sonya.harness import (
    ApprovalAlreadyDecidedError,
    ApprovalManager,
    ApprovalNotFoundError,
    ApprovalStatus,
)
from sonya.state import Substrate


@pytest.fixture()
def substrate(tmp_path: Path):
    sub = Substrate.open(tmp_path / "s.db")
    yield sub
    sub.close()


def test_create_starts_pending(substrate: Substrate) -> None:
    mgr = ApprovalManager(substrate)
    req = mgr.create(
        principal_id="ivan", action="rewrite_lifecycle", scope="self_modification"
    )
    assert req.status is ApprovalStatus.PENDING
    assert req.request_id.startswith("appr-")
    assert req.created_at


def test_get_missing_raises(substrate: Substrate) -> None:
    mgr = ApprovalManager(substrate)
    with pytest.raises(ApprovalNotFoundError):
        mgr.get("appr-does-not-exist")


def test_approve_flow(substrate: Substrate) -> None:
    mgr = ApprovalManager(substrate)
    req = mgr.create(principal_id="ivan", action="x", scope="y")
    decided = mgr.approve(req.request_id, by_principal_id="ivan-anchor")
    assert decided.status is ApprovalStatus.APPROVED
    assert decided.decided_by_principal_id == "ivan-anchor"
    assert decided.decided_at


def test_deny_flow(substrate: Substrate) -> None:
    mgr = ApprovalManager(substrate)
    req = mgr.create(principal_id="ivan", action="x", scope="y")
    decided = mgr.deny(req.request_id, by_principal_id="ivan-anchor")
    assert decided.status is ApprovalStatus.DENIED


def test_decide_twice_raises(substrate: Substrate) -> None:
    mgr = ApprovalManager(substrate)
    req = mgr.create(principal_id="ivan", action="x", scope="y")
    mgr.approve(req.request_id, by_principal_id="ivan-anchor")
    with pytest.raises(ApprovalAlreadyDecidedError):
        mgr.deny(req.request_id, by_principal_id="ivan-anchor")


def test_list_pending_returns_only_pending(substrate: Substrate) -> None:
    mgr = ApprovalManager(substrate)
    a = mgr.create(principal_id="ivan", action="a1", scope="s1")
    b = mgr.create(principal_id="ivan", action="a2", scope="s2")
    mgr.approve(a.request_id, by_principal_id="ivan-anchor")
    pending = mgr.list_pending()
    ids = [r.request_id for r in pending]
    assert a.request_id not in ids
    assert b.request_id in ids


def test_persistent_across_reopen(tmp_path: Path) -> None:
    db = tmp_path / "s.db"
    sub1 = Substrate.open(db)
    req = ApprovalManager(sub1).create(
        principal_id="ivan", action="rewrite", scope="self"
    )
    sub1.close()

    sub2 = Substrate.open(db)
    try:
        loaded = ApprovalManager(sub2).get(req.request_id)
        assert loaded.principal_id == "ivan"
        assert loaded.status is ApprovalStatus.PENDING
    finally:
        sub2.close()
