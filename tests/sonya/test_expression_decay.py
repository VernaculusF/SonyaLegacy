"""Tests for expression decay watchdog — лицо возвращается к calm после
5 минут без обновлений."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sonya.state import ContinuityStream, Substrate
from sonya.state.pending import PendingIntentionStore
from sonya.subject.internal_loop import InternalProcess


@pytest.fixture()
def proc(tmp_path: Path):
    sub = Substrate.open(tmp_path / "s.db")
    stream = ContinuityStream(sub)
    store = PendingIntentionStore(sub)
    p = InternalProcess(stream, store)
    p._substrate = sub
    yield p, sub
    sub.close()


def _set_expression(sub, marker: str, *, minutes_ago: int) -> None:
    ts = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()
    sub.connection.execute(
        "INSERT INTO subject_state(id, current_expression, updated_at) "
        "VALUES (1, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET "
        "current_expression = excluded.current_expression, "
        "updated_at = excluded.updated_at",
        (marker, ts),
    )
    sub.connection.commit()


def _read_expression(sub) -> str:
    row = sub.connection.execute(
        "SELECT current_expression FROM subject_state WHERE id = 1"
    ).fetchone()
    return (row[0] if row else "") or ""


def test_decay_ignores_calm(proc) -> None:
    p, sub = proc
    _set_expression(sub, "calm", minutes_ago=10)
    p._maybe_decay_expression()
    assert _read_expression(sub) == "calm"


def test_decay_ignores_recent_change(proc) -> None:
    p, sub = proc
    _set_expression(sub, "thinking", minutes_ago=2)
    p._maybe_decay_expression()
    assert _read_expression(sub) == "thinking"


def test_decay_resets_stale_to_calm(proc) -> None:
    p, sub = proc
    _set_expression(sub, "thinking", minutes_ago=10)
    p._maybe_decay_expression()
    assert _read_expression(sub) == "calm"


def test_decay_emits_outgoing_event(proc) -> None:
    p, sub = proc
    _set_expression(sub, "joy", minutes_ago=15)
    p._maybe_decay_expression()
    rows = sub.connection.execute(
        "SELECT kind, payload_json FROM continuity_events "
        "WHERE kind = 'outgoing.body_expression' "
        "ORDER BY seq DESC LIMIT 1"
    ).fetchone()
    assert rows is not None
    import json
    payload = json.loads(rows[1])
    assert payload["marker"] == "calm"
    assert payload["previous"] == "joy"
    assert payload["source"] == "decay"


def test_decay_idempotent(proc) -> None:
    p, sub = proc
    _set_expression(sub, "shy", minutes_ago=10)
    p._maybe_decay_expression()
    p._maybe_decay_expression()  # second call no-op
    p._maybe_decay_expression()
    decay_events = sub.connection.execute(
        "SELECT COUNT(*) FROM continuity_events "
        "WHERE kind = 'outgoing.body_expression' "
        "AND json_extract(payload_json, '$.source') = 'decay'"
    ).fetchone()[0]
    assert decay_events == 1
