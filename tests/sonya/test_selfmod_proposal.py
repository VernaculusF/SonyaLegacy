from __future__ import annotations

from pathlib import Path

import pytest

from sonya.selfmod import ProposalStatus, ProposalStore, SelfModificationProposal
from sonya.selfmod.proposal import ProposalNotFoundError
from sonya.state import Substrate


@pytest.fixture()
def store(tmp_path: Path):
    sub = Substrate.open(tmp_path / "s.db")
    yield ProposalStore(sub)
    sub.close()


def test_create_starts_draft(store: ProposalStore) -> None:
    p = store.create(
        target_module="sonya.skills.registry",
        change_summary="Add reply skill",
    )
    assert p.status is ProposalStatus.DRAFT
    assert p.proposal_id.startswith("smod-")
    assert p.target_module == "sonya.skills.registry"


def test_get_missing_raises(store: ProposalStore) -> None:
    with pytest.raises(ProposalNotFoundError):
        store.get("smod-does-not-exist")


def test_update_status(store: ProposalStore) -> None:
    p = store.create(target_module="x", change_summary="y")
    updated = store.update_status(p.proposal_id, ProposalStatus.VALIDATING)
    assert updated.status is ProposalStatus.VALIDATING
    assert updated.updated_at >= p.created_at


def test_list_by_status(store: ProposalStore) -> None:
    a = store.create(target_module="a", change_summary="a")
    b = store.create(target_module="b", change_summary="b")
    store.update_status(a.proposal_id, ProposalStatus.APPROVED)
    drafts = store.list_by_status(ProposalStatus.DRAFT)
    ids = [p.proposal_id for p in drafts]
    assert b.proposal_id in ids
    assert a.proposal_id not in ids


def test_record_validation(store: ProposalStore) -> None:
    p = store.create(target_module="x", change_summary="y")
    store.record_validation(p.proposal_id, layer=1, passed=True, reason="ok")
    store.record_validation(p.proposal_id, layer=2, passed=False, reason="test failed")
    # Verify via raw query
    rows = store._sub.connection.execute(
        "SELECT layer, passed, reason FROM self_mod_validation_results WHERE proposal_id = ? ORDER BY layer",
        (p.proposal_id,),
    ).fetchall()
    assert len(rows) == 2
    assert rows[0] == (1, 1, "ok")
    assert rows[1] == (2, 0, "test failed")


def test_persistent_across_reopen(tmp_path: Path) -> None:
    db = tmp_path / "s.db"
    sub1 = Substrate.open(db)
    p = ProposalStore(sub1).create(target_module="m", change_summary="s")
    sub1.close()

    sub2 = Substrate.open(db)
    try:
        loaded = ProposalStore(sub2).get(p.proposal_id)
        assert loaded.target_module == "m"
        assert loaded.status is ProposalStatus.DRAFT
    finally:
        sub2.close()


def test_all_statuses_are_valid() -> None:
    expected = {
        "draft", "validating", "passed_layer_1", "passed_layer_2",
        "passed_layer_3", "passed_layer_4", "requires_governed_change",
        "governed_approved", "approved", "rejected", "applied", "reverted",
    }
    actual = {s.value for s in ProposalStatus}
    assert actual == expected
