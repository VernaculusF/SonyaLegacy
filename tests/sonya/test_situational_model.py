from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sonya.state.environment import EnvironmentStore
from sonya.state.situational import SituationalStore
from sonya.state.substrate import Substrate


def test_current_assertion_supersedes_previous(tmp_path: Path) -> None:
    sub = Substrate.open(tmp_path / "test.db")
    try:
        store = SituationalStore(sub)
        first = store.assert_fact(
            subject="ivan", predicate="ivan_status", value="спит",
            source="ivan_statement", confidence=0.95,
        )
        second = store.assert_fact(
            subject="ivan", predicate="ivan_status", value="не сплю",
            source="ivan_statement", confidence=1.0,
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
        EnvironmentStore(sub).set("ivan_status", "не сплю", source="ivan_statement")
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
        assert sub.schema_version == 34
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
