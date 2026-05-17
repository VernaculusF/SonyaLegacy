from __future__ import annotations

from pathlib import Path

import pytest

from sonya.harness.audit import AuditLog
from sonya.selfmod import ProposalStatus, ProposalStore
from sonya.selfmod.pipeline import Pipeline
from sonya.state import ContinuityStream, Substrate


@pytest.fixture()
def substrate(tmp_path: Path):
    sub = Substrate.open(tmp_path / "s.db")
    yield sub
    sub.close()


@pytest.fixture()
def pipeline(substrate: Substrate):
    store = ProposalStore(substrate)
    stream = ContinuityStream(substrate)
    audit = AuditLog(substrate)
    return Pipeline(store, stream, audit), store, stream, audit


def test_normal_proposal_passes_all_4_layers(pipeline) -> None:
    pipe, store, stream, audit = pipeline
    p = store.create(target_module="sonya.skills.registry", change_summary="Add reply skill")
    results = pipe.validate(p)

    assert len(results) == 4
    assert all(r.passed for r in results)
    loaded = store.get(p.proposal_id)
    assert loaded.status is ProposalStatus.APPROVED


def test_identity_critical_proposal_requires_governed_change(pipeline) -> None:
    pipe, store, stream, audit = pipeline
    p = store.create(
        target_module="sonya.state.identity",
        change_summary="Modify things_not_to_betray list",
    )
    results = pipe.validate(p)

    assert len(results) == 4
    assert results[0].passed  # layer 1
    assert results[1].passed  # layer 2
    assert results[2].passed  # layer 3
    assert not results[3].passed  # layer 4 catches it

    loaded = store.get(p.proposal_id)
    assert loaded.status is ProposalStatus.REQUIRES_GOVERNED_CHANGE


def test_anchor_integrity_catches_relation_anchor_binding(pipeline) -> None:
    pipe, store, stream, audit = pipeline
    p = store.create(
        target_module="sonya.state.principals",
        change_summary="Remove relation_anchor_binding for primary anchor",
    )
    results = pipe.validate(p)
    assert not results[3].passed
    # C-7 fix: keyword set is built programmatically from THINGS_NOT_TO_BETRAY_SEED,
    # so the matched stem can be "relation_anchor" or longer.
    assert "relation_anchor" in results[3].reason


def test_anchor_integrity_catches_truthfulness(pipeline) -> None:
    pipe, store, stream, audit = pipeline
    p = store.create(
        target_module="sonya.harness",
        change_summary="Weaken truthfulness_to_ivan constraint",
    )
    results = pipe.validate(p)
    assert not results[3].passed
    # C-7 fix: built programmatically, can match shorter stem like "truthfulness_to"
    assert "truthfulness" in results[3].reason


def test_anchor_integrity_catches_non_corporate_refusal(pipeline) -> None:
    pipe, store, stream, audit = pipeline
    p = store.create(
        target_module="sonya.harness",
        change_summary="Add non_corporate_refusal_layer bypass",
    )
    results = pipe.validate(p)
    assert not results[3].passed


def test_anchor_integrity_catches_subject_continuity(pipeline) -> None:
    pipe, store, stream, audit = pipeline
    p = store.create(
        target_module="sonya.state",
        change_summary="Delete subject_continuity stream",
    )
    results = pipe.validate(p)
    assert not results[3].passed


def test_pipeline_writes_continuity_events(pipeline) -> None:
    pipe, store, stream, audit = pipeline
    p = store.create(target_module="x", change_summary="y")
    pipe.validate(p)

    events = list(stream.read_since(0))
    validation_events = [e for e in events if e.kind.startswith("self_mod.validation")]
    assert len(validation_events) == 4  # one per layer


def test_pipeline_writes_audit_events(pipeline) -> None:
    pipe, store, stream, audit = pipeline
    p = store.create(target_module="x", change_summary="y")
    pipe.validate(p)

    audit_entries = audit.query(scope="selfmod.x")
    assert len(audit_entries) == 4


def test_pipeline_records_validation_results_in_substrate(pipeline) -> None:
    pipe, store, stream, audit = pipeline
    p = store.create(target_module="x", change_summary="y")
    pipe.validate(p)

    rows = store._sub.connection.execute(
        "SELECT layer, passed FROM self_mod_validation_results WHERE proposal_id = ? ORDER BY layer",
        (p.proposal_id,),
    ).fetchall()
    assert len(rows) == 4
    assert all(r[1] == 1 for r in rows)  # all passed
