from __future__ import annotations

from pathlib import Path

import pytest

from sonya.state import Substrate, SubstrateVersionError


def test_fresh_substrate_creates_at_writable_version(tmp_path: Path) -> None:
    db = tmp_path / "s.db"
    sub = Substrate.open(db)
    try:
        assert sub.schema_version == Substrate.WRITABLE_VERSION
        assert db.exists()
    finally:
        sub.close()


def test_open_substrate_with_unknown_future_version_refuses(tmp_path: Path) -> None:
    db = tmp_path / "s.db"
    Substrate.open(db).close()
    # Bump schema_version manually to something we cannot read.
    import sqlite3
    with sqlite3.connect(db) as conn:
        conn.execute("UPDATE schema_version SET version = ?", (999,))
        conn.commit()
    with pytest.raises(SubstrateVersionError):
        Substrate.open(db)


def test_substrate_close_releases_connection(tmp_path: Path) -> None:
    db = tmp_path / "s.db"
    sub = Substrate.open(db)
    sub.close()
    # Reopening must succeed (no lingering lock).
    sub2 = Substrate.open(db)
    sub2.close()


def test_substrate_creates_parent_dirs(tmp_path: Path) -> None:
    db = tmp_path / "deeply" / "nested" / "s.db"
    sub = Substrate.open(db)
    try:
        assert db.exists()
    finally:
        sub.close()


def test_substrate_exposes_connection(tmp_path: Path) -> None:
    sub = Substrate.open(tmp_path / "s.db")
    try:
        cursor = sub.connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        # Schema sanity: at least our core tables exist.
        assert "schema_version" in tables
        assert "subject_state" in tables
        assert "continuity_events" in tables
        assert "continuity_snapshots" in tables
        assert "identity_record" in tables
        assert "relation_anchor_bindings" in tables
        assert "principals" in tables
    finally:
        sub.close()


def test_read_only_open_does_not_create_db(tmp_path: Path) -> None:
    db = tmp_path / "missing.db"
    with pytest.raises(FileNotFoundError):
        Substrate.open(db, read_only=True)
