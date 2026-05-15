from __future__ import annotations

from pathlib import Path

import pytest

from sonya.selfmod import ProposalStatus, ProposalStore
from sonya.selfmod.watchdog import WatchWindow
from sonya.state import ContinuityStream, Substrate


@pytest.fixture()
def substrate(tmp_path: Path):
    sub = Substrate.open(tmp_path / "s.db")
    yield sub
    sub.close()


def test_confirm_stable_marks_applied(substrate: Substrate) -> None:
    store = ProposalStore(substrate)
    stream = ContinuityStream(substrate)
    watchdog = WatchWindow(store, stream)

    p = store.create(target_module="x", change_summary="y")
    store.update_status(p.proposal_id, ProposalStatus.APPROVED)

    watchdog.confirm_stable(p)

    loaded = store.get(p.proposal_id)
    assert loaded.status is ProposalStatus.APPLIED

    events = list(stream.read_since(0))
    stable_events = [e for e in events if e.kind == "self_mod.confirmed_stable"]
    assert len(stable_events) == 1


def test_trigger_revert_marks_reverted(substrate: Substrate) -> None:
    store = ProposalStore(substrate)
    stream = ContinuityStream(substrate)
    watchdog = WatchWindow(store, stream)

    p = store.create(target_module="x", change_summary="y")
    store.update_status(p.proposal_id, ProposalStatus.APPLIED)

    watchdog.trigger_revert(p, reason="anchor drift detected")

    loaded = store.get(p.proposal_id)
    assert loaded.status is ProposalStatus.REVERTED

    events = list(stream.read_since(0))
    revert_events = [e for e in events if e.kind == "self_mod.auto_reverted"]
    assert len(revert_events) == 1
    assert revert_events[0].payload["reason"] == "anchor drift detected"


def test_check_drift_signal_stub_returns_false(substrate: Substrate) -> None:
    store = ProposalStore(substrate)
    stream = ContinuityStream(substrate)
    watchdog = WatchWindow(store, stream)

    p = store.create(target_module="x", change_summary="y")
    assert watchdog.check_drift_signal(p) is False
