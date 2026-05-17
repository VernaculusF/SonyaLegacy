from __future__ import annotations

from pathlib import Path

import pytest

from sonya.selfmod import ProposalStore
from sonya.skills.gap_detector import GapDetector
from sonya.state import ContinuityEvent, ContinuityStream, Substrate


@pytest.fixture()
def substrate(tmp_path: Path):
    sub = Substrate.open(tmp_path / "s.db")
    yield sub
    sub.close()


def test_scan_detects_gap_from_failed_action(substrate: Substrate) -> None:
    stream = ContinuityStream(substrate)
    # Use a non-skipped kind. cognitive_tick is intentionally skipped now —
    # otherwise gap detector self-triggers on every idle tick.
    stream.append(ContinuityEvent(
        kind="harness.policy_decision",
        payload={"triggers": ["failed_action:reply_via_telegram"]},
    ))

    detector = GapDetector(substrate, stream)
    gaps = detector.scan_recent(since_seq=0)
    assert len(gaps) == 1
    assert "failed_action" in gaps[0].description


def test_scan_ignores_normal_events(substrate: Substrate) -> None:
    stream = ContinuityStream(substrate)
    stream.append(ContinuityEvent(
        kind="harness.policy_decision",
        payload={"triggers": ["idle_timeout"], "counters": {"loneliness": 0.5}},
    ))

    detector = GapDetector(substrate, stream)
    gaps = detector.scan_recent(since_seq=0)
    assert len(gaps) == 0


def test_create_proposal_from_gap(substrate: Substrate) -> None:
    stream = ContinuityStream(substrate)
    stream.append(ContinuityEvent(
        kind="harness.policy_decision",
        payload={"triggers": ["missing_capability:tg_reply"]},
    ))

    detector = GapDetector(substrate, stream)
    gaps = detector.scan_recent(since_seq=0)
    assert len(gaps) == 1

    proposal_store = ProposalStore(substrate)
    proposal_id = detector.create_proposal_from_gap(gaps[0], proposal_store)
    assert proposal_id.startswith("smod-")

    # Gap should be marked as proposed
    row = substrate.connection.execute(
        "SELECT status, proposal_id FROM capability_gaps WHERE gap_id = ?",
        (gaps[0].gap_id,),
    ).fetchone()
    assert row[0] == "proposed"
    assert row[1] == proposal_id


def test_gap_persistent(substrate: Substrate) -> None:
    stream = ContinuityStream(substrate)
    stream.append(ContinuityEvent(
        kind="x", payload={"triggers": ["cannot:do_thing"]},
    ))
    detector = GapDetector(substrate, stream)
    gaps = detector.scan_recent(since_seq=0)
    assert len(gaps) == 1

    # Verify in DB
    row = substrate.connection.execute(
        "SELECT gap_id, status FROM capability_gaps"
    ).fetchone()
    assert row[0] == gaps[0].gap_id
    assert row[1] == "open"
