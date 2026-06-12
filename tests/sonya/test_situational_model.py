from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sonya.state.environment import EnvironmentStore
from sonya.state.continuity_stream import ContinuityEvent, ContinuityStream
from sonya.state.situational import (
    SituationalStore, 
    record_ivan_activity,
    SituationalMetrics,
    CredentialExposureStore
)
from sonya.state.substrate import Substrate


def test_current_assertion_supersedes_previous(tmp_path: Path) -> None:
    sub = Substrate.open(tmp_path / "test.db")
    try:
        store = SituationalStore(sub)
        first = store.assert_fact(
            subject="ivan", predicate="ivan_status", value="спит",
            source="ivan_said", confidence=0.95,
        )
        second = store.assert_fact(
            subject="ivan", predicate="ivan_status", value="не сплю",
            source="ivan_said", confidence=1.0,
        )
        assert second.supersedes_id == first.assertion_id
        assert store.get_current(subject="ivan", predicate="ivan_status").value == "не сплю"
        active = sub.connection.execute(
            "SELECT active FROM situational_assertions WHERE assertion_id = ?",
            (first.assertion_id,),
        ).fetchone()
        assert active == (0,)
    finally:
        sub.close()


def test_expired_assertion_is_not_current(tmp_path: Path) -> None:
    sub = Substrate.open(tmp_path / "test.db")
    try:
        expired = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
        SituationalStore(sub).assert_fact(
            subject="ivan", predicate="ivan_status", value="занят", expires_at=expired
        )
        assert SituationalStore(sub).get_current(
            subject="ivan", predicate="ivan_status"
        ) is None
    finally:
        sub.close()


def test_environment_facade_routes_ivan_status_to_ivan(tmp_path: Path) -> None:
    sub = Substrate.open(tmp_path / "test.db")
    try:
        EnvironmentStore(sub).set("ivan_status", "не сплю", source="ivan_said")
        item = EnvironmentStore(sub).get("ivan_status")
        assert item is not None
        assert item["subject"] == "ivan"
        assert item["value"] == "не сплю"
    finally:
        sub.close()


def test_environment_facade_rejects_credentials(tmp_path: Path) -> None:
    sub = Substrate.open(tmp_path / "test.db")
    try:
        with pytest.raises(ValueError, match="protected secret storage"):
            EnvironmentStore(sub).set("apikey_shodan", "secret-value")
    finally:
        sub.close()


def test_runtime_state_is_not_in_environment_view(tmp_path: Path) -> None:
    from sonya.state.runtime_state import RuntimeStateStore

    sub = Substrate.open(tmp_path / "test.db")
    try:
        RuntimeStateStore(sub).set("atrium_last_seen", "2026-06-12T00:00:00+00:00")
        assert EnvironmentStore(sub).get("atrium_last_seen") is None
        assert "atrium_last_seen" not in EnvironmentStore(sub).list_all()
    finally:
        sub.close()


def test_incoming_ivan_activity_invalidates_sleep_status(tmp_path: Path) -> None:
    sub = Substrate.open(tmp_path / "test.db")
    try:
        EnvironmentStore(sub).set("ivan_status", "спит", source="ivan_said")
        stream = ContinuityStream(sub)
        incoming = stream.append(ContinuityEvent(
            kind="incoming.atrium_dialog",
            principal_id="ivan",
            payload={"text": "я не сплю"},
        ))
        updated = record_ivan_activity(
            sub,
            source="incoming.atrium_dialog",
            source_ref=str(incoming.seq),
            stream=stream,
        )
        assert updated is not None
        current = EnvironmentStore(sub).get("ivan_status")
        assert current["value"] == "active"
        assert current["source"] == "incoming.atrium_dialog"
        events = list(stream.read_since(0))
        assert any(e.kind == "world_state.ivan_activity_invalidated_status" for e in events)
    finally:
        sub.close()


def test_incoming_ivan_activity_does_not_overwrite_specific_active_status(tmp_path: Path) -> None:
    sub = Substrate.open(tmp_path / "test.db")
    try:
        EnvironmentStore(sub).set("ivan_status", "работает", source="ivan_said")
        updated = record_ivan_activity(sub, source="incoming.atrium_dialog")
        assert updated is None
        assert EnvironmentStore(sub).get("ivan_status")["value"] == "работает"
    finally:
        sub.close()


def test_v33_migration_removes_credential_values_and_records_exposure(tmp_path: Path) -> None:
    path = tmp_path / "legacy.db"
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE schema_version(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
        INSERT INTO schema_version VALUES (33, '2026-06-12T00:00:00+00:00');
        CREATE TABLE environment_state (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL,
            updated_by TEXT NOT NULL DEFAULT ''
        );
        INSERT INTO environment_state VALUES
            ('ivan_status', 'спит', 'ivan_statement', '2026-06-12T00:00:00+00:00', 'agent'),
            ('atrium_last_seen', '2026-06-12T00:00:00+00:00', 'system', '2026-06-12T00:00:00+00:00', 'atrium'),
            ('apikey_shodan', 'raw-secret-value', 'observation', '2026-06-12T00:00:00+00:00', 'agent');
    """)
    conn.commit()
    conn.close()

    sub = Substrate.open(path)
    try:
        assert sub.schema_version >= 34
        assert EnvironmentStore(sub).get("ivan_status")["value"] == "спит"
        assert EnvironmentStore(sub).get("atrium_last_seen") is None
        assert sub.connection.execute(
            "SELECT value FROM runtime_state WHERE key = 'atrium_last_seen'"
        ).fetchone() == ("2026-06-12T00:00:00+00:00",)
        assert EnvironmentStore(sub).get("apikey_shodan") is None
        exposure = sub.connection.execute(
            "SELECT credential_label, metadata_json FROM credential_exposures"
        ).fetchone()
        assert exposure[0] == "apikey_shodan"
        assert "raw-secret-value" not in exposure[1]
        assert sub.connection.execute(
            "SELECT COUNT(*) FROM environment_state"
        ).fetchone() == (0,)
    finally:
        sub.close()


def test_invalidates_ids_handles_contradictions(tmp_path: Path) -> None:
    sub = Substrate.open(tmp_path / "test.db")
    try:
        store = SituationalStore(sub)
        
        # Original fact
        f1 = store.assert_fact(subject="ivan", predicate="status", value="sleeping", source="system")
        
        # Another fact that logically contradicts it
        f2 = store.assert_fact(subject="ivan", predicate="activity", value="typing", source="observation", invalidates_ids=[f1.assertion_id])
        
        # Ensure f1 is inactive and superseded by f2
        active = sub.connection.execute(
            "SELECT active, superseded_by FROM situational_assertions WHERE assertion_id = ?",
            (f1.assertion_id,)
        ).fetchone()
        assert active[0] == 0
        assert active[1] == f2.assertion_id
        
    finally:
        sub.close()


def test_situational_metrics(tmp_path: Path) -> None:
    sub = Substrate.open(tmp_path / "test.db")
    try:
        store = SituationalStore(sub)
        metrics = SituationalMetrics(sub)
        
        # stale fact
        expired = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
        store.assert_fact(subject="test", predicate="stale", value="yes", expires_at=expired, source="system")
        
        # low confidence
        store.assert_fact(subject="test", predicate="guess", value="maybe", confidence=0.3, source="hypothesis")
        
        # high confidence active
        store.assert_fact(subject="test", predicate="fact", value="yes", confidence=0.9, source="observation")
        
        # invalidated
        f1 = store.assert_fact(subject="test", predicate="wrong", value="no", source="system")
        store.assert_fact(subject="test", predicate="wrong", value="yes", invalidates_ids=[f1.assertion_id], source="observation")
        
        res = metrics.calculate()
        assert res.total_active == 4
        assert res.stale_active == 1
        assert res.low_confidence == 1
        assert res.invalidated_count == 1
        
        # test1 provided one stale active and one invalidated.
        assert len(res.frequent_sources) > 0
        
    finally:
        sub.close()


def test_credential_exposure_store(tmp_path: Path) -> None:
    sub = Substrate.open(tmp_path / "test.db")
    try:
        store = CredentialExposureStore(sub)
        
        # record
        e1 = store.record_exposure(source_kind="env.set", credential_label="aws_key", source_ref="sys")
        assert e1.status == "unresolved"
        
        e2 = store.record_exposure(source_kind="scan", credential_label="db_pass")
        
        # list unresolved
        unresolved = store.list_unresolved()
        assert len(unresolved) == 2
        labels = {e.credential_label for e in unresolved}
        assert labels == {"aws_key", "db_pass"}
        
        # resolve
        assert store.resolve(e1.exposure_id, note="rotated") is True
        assert store.resolve(e1.exposure_id) is False # already resolved
        
        unresolved_after = store.list_unresolved()
        assert len(unresolved_after) == 1
        assert unresolved_after[0].credential_label == "db_pass"
        
    finally:
        sub.close()


def test_refute_fact_prevents_silent_repromotion(tmp_path: Path) -> None:
    sub = Substrate.open(tmp_path / "test.db")
    try:
        store = SituationalStore(sub)
        
        store.assert_fact(subject="ivan", predicate="status", value="sleeping", source="observation")
        assert store.get_current(subject="ivan", predicate="status").value == "sleeping"

        refuted = store.refute_fact(subject="ivan", predicate="status", reason="he just texted me")
        assert refuted.value == "[REFUTED]"
        assert refuted.metadata["refuted_value"] == "sleeping"

        assert store.get_current(subject="ivan", predicate="status") is None

        items = store.list_current(subject="ivan")
        assert all(i.value != "[REFUTED]" for i in items)

        import pytest
        with pytest.raises(ValueError, match="Cannot silently re-promote refuted fact"):
            store.assert_fact(subject="ivan", predicate="status", value="sleeping", source="observation")
        
        store.assert_fact(subject="ivan", predicate="status", value="sleeping", source="observation", force_repromote=True)
        assert store.get_current(subject="ivan", predicate="status").value == "sleeping"

        store.refute_fact(subject="ivan", predicate="status", reason="woke up")
        store.assert_fact(subject="ivan", predicate="status", value="active", source="observation")
        assert store.get_current(subject="ivan", predicate="status").value == "active"
    finally:
        sub.close()

def test_trust_context_and_history(tmp_path: Path) -> None:
    from sonya.state.situational import TrustContext
    sub = Substrate.open(tmp_path / "test.db")
    try:
        store = SituationalStore(sub)
        tctx: TrustContext = {"authority_level": "authoritative", "trust_signals": ["system_derived"]}
        
        f1 = store.assert_fact(subject="ivan", predicate="mood", value="happy", source="system", trust_context=tctx)
        
        # Verify trust_context is persisted
        curr = store.get_current(subject="ivan", predicate="mood")
        assert curr is not None
        assert curr.metadata.get("trust") == {"authority_level": "authoritative", "trust_signals": ["system_derived"]}
        
        f2 = store.assert_fact(subject="ivan", predicate="mood", value="sad", source="system")
        
        f3 = store.assert_fact(subject="ivan", predicate="status", value="sleeping", source="system")
        f4 = store.assert_fact(subject="ivan", predicate="status", value="awake", source="system", invalidates_ids=[f3.assertion_id, f2.assertion_id])
        
        history_f4 = store.get_assertion_history(f4.assertion_id)
        # f4 invalidated f3 and f2. f2 superseded f1. So the tree includes f1, f2, f3, f4.
        ids = {h.assertion_id for h in history_f4}
        assert ids == {f1.assertion_id, f2.assertion_id, f3.assertion_id, f4.assertion_id}
        
    finally:
        sub.close()
