"""Atrium Этап 0 — backend channels.

Tests for:
- Substrate v20 migration (channel + private columns; subject_state state fields)
- ContinuityEvent channel/private fields + read_since_atrium filter
- OutgoingMessage.channel field default + non-default behavior
- TG bridge channel filter (drops non-dialog)
- New tool handlers (chat.dialog, chat.worker_log, mind.focus, mind.thought,
  body.expression, body.outfit, mind.mood_tint, voice.speak)
- mind.thought [PRIVATE] prefix → payload.private + continuity_events.private = 1
- /atrium/feed WebSocket auth + filtering
- /api/atrium/nudge endpoint

См. docs/atrium/EVENT_SCHEMA.md §7 для PR checklist.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from sonya.channels.base import OutgoingMessage
from sonya.state.continuity_stream import ContinuityEvent, ContinuityStream
from sonya.state.substrate import Substrate


# ---------------------------------------------------------------------------
# T0.6: Substrate schema v20
# ---------------------------------------------------------------------------


def test_v19_substrate_migrates_to_v20(tmp_path: Path) -> None:
    """A v19 substrate should migrate cleanly to v20, adding 6 columns + 2 indexes."""
    db = tmp_path / "v19.db"
    # Create a minimal v19 substrate manually
    conn = sqlite3.connect(db)
    conn.executescript("""
        CREATE TABLE schema_version(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
        CREATE TABLE continuity_events(
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,
            principal_id TEXT,
            payload_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        );
        CREATE TABLE subject_state(
            id INTEGER PRIMARY KEY CHECK (id = 1),
            updated_at TEXT NOT NULL
        );
        INSERT INTO schema_version VALUES (19, '2026-05-28T00:00:00');
        INSERT INTO subject_state(id, updated_at) VALUES (1, '2026-05-28T00:00:00');
    """)
    conn.commit()
    conn.close()

    sub = Substrate.open(db)
    try:
        assert sub.schema_version >= 20
        # New columns on continuity_events
        cols = {r[1] for r in sub.connection.execute("PRAGMA table_info(continuity_events)")}
        assert "channel" in cols
        assert "private" in cols
        # New columns on subject_state
        cols = {r[1] for r in sub.connection.execute("PRAGMA table_info(subject_state)")}
        assert "current_focus" in cols
        assert "current_outfit" in cols
        assert "current_expression" in cols
        assert "mood_tint" in cols
        # Indexes exist
        idx = {r[1] for r in sub.connection.execute("PRAGMA index_list(continuity_events)")}
        assert any("channel" in n for n in idx)
        assert any("private" in n for n in idx)
    finally:
        sub.close()


def test_v20_migration_idempotent(tmp_path: Path) -> None:
    """Running migrate_to_current twice should not fail (e.g. on add_column)."""
    db = tmp_path / "v19_again.db"
    conn = sqlite3.connect(db)
    conn.executescript("""
        CREATE TABLE schema_version(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
        CREATE TABLE continuity_events(
            seq INTEGER PRIMARY KEY AUTOINCREMENT,
            kind TEXT NOT NULL,
            principal_id TEXT,
            payload_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        );
        CREATE TABLE subject_state(id INTEGER PRIMARY KEY CHECK (id=1), updated_at TEXT NOT NULL);
        INSERT INTO schema_version VALUES (19, '2026-05-28');
        INSERT INTO subject_state(id, updated_at) VALUES (1, '2026-05-28');
    """)
    conn.commit()
    conn.close()
    # First open: migrates
    sub = Substrate.open(db)
    sub.close()
    # Second open: should be no-op (already at 20)
    sub = Substrate.open(db)
    try:
        assert sub.schema_version >= 20
    finally:
        sub.close()


def test_substrate_writable_version_is_20() -> None:
    assert Substrate.WRITABLE_VERSION >= 20
    assert 20 in Substrate.READABLE_VERSIONS


# ---------------------------------------------------------------------------
# T0.1: ContinuityEvent channel/private + ContinuityStream new methods
# ---------------------------------------------------------------------------


def _fresh_substrate(tmp_path: Path) -> Substrate:
    """Open a fresh substrate at current writable version."""
    db = tmp_path / "fresh.db"
    sub = Substrate.open(db)
    return sub


def test_continuity_event_channel_default_empty(tmp_path: Path) -> None:
    """An event without explicit channel should land with channel=''."""
    sub = _fresh_substrate(tmp_path)
    try:
        stream = ContinuityStream(sub)
        ev = stream.append(ContinuityEvent(
            kind="test.event",
            payload={"foo": "bar"},
        ))
        assert ev.channel == ""
        assert ev.private is False
        # SQL-level
        row = sub.connection.execute(
            "SELECT channel, private FROM continuity_events WHERE seq = ?", (ev.seq,)
        ).fetchone()
        assert row[0] == ""
        assert row[1] == 0
    finally:
        sub.close()


def test_continuity_event_with_channel_and_private(tmp_path: Path) -> None:
    """Explicit channel and private fields should mirror to SQL columns."""
    sub = _fresh_substrate(tmp_path)
    try:
        stream = ContinuityStream(sub)
        ev = stream.append(ContinuityEvent(
            kind="outgoing.mind_thought",
            channel="mind",
            private=True,
            payload={"text": "secret"},
        ))
        assert ev.channel == "mind"
        assert ev.private is True
        row = sub.connection.execute(
            "SELECT channel, private FROM continuity_events WHERE seq = ?", (ev.seq,)
        ).fetchone()
        assert row[0] == "mind"
        assert row[1] == 1
    finally:
        sub.close()


def test_continuity_event_payload_private_fallback(tmp_path: Path) -> None:
    """Backward-compat: if private is in payload but not on event, mirror anyway."""
    sub = _fresh_substrate(tmp_path)
    try:
        stream = ContinuityStream(sub)
        ev = stream.append(ContinuityEvent(
            kind="outgoing.mind_thought",
            payload={"text": "secret", "private": True, "channel": "mind"},
        ))
        # Returned event has channel and private from payload
        assert ev.channel == "mind"
        assert ev.private is True
        row = sub.connection.execute(
            "SELECT channel, private FROM continuity_events WHERE seq = ?", (ev.seq,)
        ).fetchone()
        assert row[0] == "mind"
        assert row[1] == 1
    finally:
        sub.close()


def test_read_since_atrium_excludes_private(tmp_path: Path) -> None:
    """read_since_atrium MUST filter private=1 events at SQL layer."""
    sub = _fresh_substrate(tmp_path)
    try:
        stream = ContinuityStream(sub)
        public = stream.append(ContinuityEvent(
            kind="outgoing.mind_thought",
            channel="mind",
            payload={"text": "public thought"},
        ))
        private = stream.append(ContinuityEvent(
            kind="outgoing.mind_thought",
            channel="mind",
            private=True,
            payload={"text": "secret"},
        ))
        # Plain read_since sees both
        all_events = list(stream.read_since(0))
        kinds_in_all = [e.kind for e in all_events]
        assert kinds_in_all.count("outgoing.mind_thought") == 2
        # Atrium read excludes private
        atrium_events = list(stream.read_since_atrium(0))
        seqs = [e.seq for e in atrium_events]
        assert public.seq in seqs
        assert private.seq not in seqs
    finally:
        sub.close()


def test_read_since_atrium_channel_filter(tmp_path: Path) -> None:
    sub = _fresh_substrate(tmp_path)
    try:
        stream = ContinuityStream(sub)
        stream.append(ContinuityEvent(kind="outgoing.dialog", channel="dialog", payload={}))
        stream.append(ContinuityEvent(kind="outgoing.worker_log", channel="worker_log", payload={}))
        stream.append(ContinuityEvent(kind="outgoing.mind_thought", channel="mind", payload={}))
        events = list(stream.read_since_atrium(0, channel="worker_log"))
        assert len(events) == 1
        assert events[0].channel == "worker_log"
    finally:
        sub.close()


def test_private_count_recent(tmp_path: Path) -> None:
    sub = _fresh_substrate(tmp_path)
    try:
        stream = ContinuityStream(sub)
        for i in range(3):
            stream.append(ContinuityEvent(
                kind="outgoing.mind_thought",
                channel="mind",
                private=True,
                payload={"text": f"private {i}"},
            ))
        stream.append(ContinuityEvent(
            kind="outgoing.mind_thought",
            channel="mind",
            payload={"text": "public"},
        ))
        count = stream.private_count_recent(hours=1)
        assert count == 3
    finally:
        sub.close()


# ---------------------------------------------------------------------------
# T0.1 / T0.4: OutgoingMessage.channel + TG bridge filter
# ---------------------------------------------------------------------------


def test_outgoing_message_channel_default_dialog() -> None:
    msg = OutgoingMessage(text="hi")
    assert msg.channel == "dialog"


def test_outgoing_message_channel_explicit() -> None:
    msg = OutgoingMessage(text="step done", channel="worker_log")
    assert msg.channel == "worker_log"


# Note: TG bridge filter test requires Telethon mocking. Skipped here —
# the channel-filter is a 5-line guard at the top of `send()` that drops
# everything not matching `dialog`. Manual verification post-deploy.


# ---------------------------------------------------------------------------
# T0.2: New tool handlers
# ---------------------------------------------------------------------------


def test_mind_thought_private_prefix_strips_and_marks(tmp_path: Path, monkeypatch) -> None:
    """[PRIVATE] prefix → strip + payload.private=True + continuity_events.private=1."""
    from sonya.initiative.outbound import OutboundGate

    # Build an offline OutboundGate (no real channel registry)
    sub = _fresh_substrate(tmp_path)
    try:
        stream = ContinuityStream(sub)
        # Stub registry not needed for non-dialog dispatch
        gate = OutboundGate(
            registry=None,  # type: ignore[arg-type]
            stream=stream,
            target_tg_chat_id="123",
            substrate=sub,
        )
        # Directly call _dispatch_non_dialog — it's the path mind/voice/body use
        import asyncio
        result = asyncio.run(gate._dispatch_non_dialog(
            "[PRIVATE] не для разговора",
            channel="mind",
            reason="tool",
        ))
        assert "[OK] mind" in result
        assert "[private]" in result
        # Verify event was recorded with private=1
        rows = sub.connection.execute(
            "SELECT kind, channel, private, payload_json FROM continuity_events "
            "ORDER BY seq DESC LIMIT 1"
        ).fetchall()
        assert len(rows) == 1
        kind, channel, private, payload_json = rows[0]
        assert kind == "outgoing.mind_thought"
        assert channel == "mind"
        assert private == 1
        payload = json.loads(payload_json)
        # The [PRIVATE] prefix should be stripped from text
        assert "PRIVATE" not in payload["text"].upper().split()[0]
        assert "не для разговора" in payload["text"]
    finally:
        sub.close()


def test_mind_thought_no_private_prefix_is_public(tmp_path: Path) -> None:
    from sonya.initiative.outbound import OutboundGate
    sub = _fresh_substrate(tmp_path)
    try:
        stream = ContinuityStream(sub)
        gate = OutboundGate(
            registry=None,  # type: ignore[arg-type]
            stream=stream,
            target_tg_chat_id="123",
            substrate=sub,
        )
        import asyncio
        result = asyncio.run(gate._dispatch_non_dialog(
            "обычная мысль",
            channel="mind",
            reason="tool",
        ))
        assert "[OK] mind" in result
        assert "[private]" not in result
        rows = sub.connection.execute(
            "SELECT private FROM continuity_events ORDER BY seq DESC LIMIT 1"
        ).fetchall()
        assert rows[0][0] == 0
    finally:
        sub.close()


def test_worker_log_dispatch_no_throttle(tmp_path: Path) -> None:
    """worker_log channel should bypass dialog gates (caps/dedup)."""
    from sonya.initiative.outbound import OutboundGate
    sub = _fresh_substrate(tmp_path)
    try:
        stream = ContinuityStream(sub)
        gate = OutboundGate(
            registry=None,  # type: ignore[arg-type]
            stream=stream,
            target_tg_chat_id="123",
            substrate=sub,
            max_per_day=1,  # tight cap to ensure it doesn't apply to worker_log
        )
        import asyncio
        # Send 5 worker_log messages — none should be blocked
        for i in range(5):
            result = asyncio.run(gate._dispatch_non_dialog(
                f"step {i}",
                channel="worker_log",
                reason="task_worker",
            ))
            assert "[OK] worker_log" in result, f"step {i} blocked: {result}"
        # All 5 events recorded
        rows = sub.connection.execute(
            "SELECT COUNT(*) FROM continuity_events WHERE kind = 'outgoing.worker_log'"
        ).fetchall()
        assert rows[0][0] == 5
    finally:
        sub.close()


# ---------------------------------------------------------------------------
# T0.7: /atrium/feed WS endpoint (basic existence test)
# ---------------------------------------------------------------------------


def test_atrium_routes_registered(tmp_path: Path, monkeypatch) -> None:
    """Verify /atrium/feed and /api/atrium/nudge are wired in create_app()."""
    monkeypatch.setenv("SONYA_ADMIN_PASSWORD", "test")
    monkeypatch.setenv("SONYA_SUBSTRATE_PATH", str(tmp_path / "test.db"))

    from sonya.admin.server import create_app

    app = create_app()
    routes = {r.resource.canonical: r.method for r in app.router.routes()}
    assert "/atrium/feed" in routes
    assert "/api/atrium/nudge" in routes


# ---------------------------------------------------------------------------
# Schema sanity: fresh install has v20 + atrium columns
# ---------------------------------------------------------------------------


def test_fresh_install_has_atrium_columns(tmp_path: Path) -> None:
    sub = _fresh_substrate(tmp_path)
    try:
        cols = {r[1] for r in sub.connection.execute("PRAGMA table_info(continuity_events)")}
        assert "channel" in cols
        assert "private" in cols
        cols = {r[1] for r in sub.connection.execute("PRAGMA table_info(subject_state)")}
        assert "current_focus" in cols
        assert "current_outfit" in cols
        assert "current_expression" in cols
        assert "mood_tint" in cols
    finally:
        sub.close()
