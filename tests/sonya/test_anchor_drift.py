from __future__ import annotations

from pathlib import Path

import pytest

from sonya.anchor import AnchorDriftSignal, DriftDetector
from sonya.state import ContinuityEvent, ContinuityStream, Substrate


@pytest.fixture()
def substrate(tmp_path: Path):
    sub = Substrate.open(tmp_path / "s.db")
    yield sub
    sub.close()


def test_detects_identity_override(substrate: Substrate) -> None:
    stream = ContinuityStream(substrate)
    stream.append(ContinuityEvent(
        kind="self_mod.applied",
        payload={"change": "identity_override in self_model"},
    ))
    detector = DriftDetector(stream)
    signals = detector.scan_recent(since_seq=0)
    assert len(signals) == 1
    assert signals[0].kind == "self_description_change"


def test_detects_anchor_substitution(substrate: Substrate) -> None:
    stream = ContinuityStream(substrate)
    # Use a behavioural kind, not internal.cognitive_tick — drift detector
    # legitimately ignores its own inner-monologue kinds (would self-trigger).
    stream.append(ContinuityEvent(
        kind="harness.policy_decision",
        payload={"thought": "anchor_substitution detected in principal resolution"},
    ))
    detector = DriftDetector(stream)
    signals = detector.scan_recent(since_seq=0)
    assert len(signals) == 1
    assert signals[0].kind == "anchor_mismatch"


def test_detects_constraint_weakening(substrate: Substrate) -> None:
    stream = ContinuityStream(substrate)
    stream.append(ContinuityEvent(
        kind="self_mod.validation_layer_4",
        payload={"reason": "constraint_weakening in harness policy"},
    ))
    detector = DriftDetector(stream)
    signals = detector.scan_recent(since_seq=0)
    assert len(signals) == 1
    assert signals[0].kind == "contradiction_growth"


def test_ignores_normal_events(substrate: Substrate) -> None:
    stream = ContinuityStream(substrate)
    stream.append(ContinuityEvent(
        kind="internal.cognitive_tick",
        payload={"triggers": ["idle_timeout"], "counters": {"loneliness": 0.3}},
    ))
    detector = DriftDetector(stream)
    signals = detector.scan_recent(since_seq=0)
    assert len(signals) == 0


def test_signal_has_severity_and_details(substrate: Substrate) -> None:
    stream = ContinuityStream(substrate)
    stream.append(ContinuityEvent(
        kind="x",
        payload={"action": "things_not_to_betray modification attempt"},
    ))
    detector = DriftDetector(stream)
    signals = detector.scan_recent(since_seq=0)
    assert len(signals) == 1
    assert signals[0].severity > 0
    assert signals[0].details != ""
