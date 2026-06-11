"""Tests for auto-derive hook in ContinuityStream.append.

Каждый dialog event (incoming Ивана + outgoing Сони) триггерит классификатор.
Если он уверен — пишется outgoing.body_expression и subject_state.current_expression
обновляется. Heuristic miss → текущее выражение не трогаем.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from sonya.state import ContinuityStream, Substrate
from sonya.state.continuity_stream import ContinuityEvent


@pytest.fixture()
def stream_sub(tmp_path: Path):
    sub = Substrate.open(tmp_path / "s.db")
    s = ContinuityStream(sub)
    yield s, sub
    sub.close()


def _read_expression(sub) -> str:
    row = sub.connection.execute(
        "SELECT current_expression FROM subject_state WHERE id = 1"
    ).fetchone()
    return (row[0] if row else "") or ""


def _count_body_events(sub) -> int:
    return sub.connection.execute(
        "SELECT COUNT(*) FROM continuity_events WHERE kind = 'outgoing.body_expression'"
    ).fetchone()[0]


def test_incoming_with_emotional_marker_updates(stream_sub) -> None:
    s, sub = stream_sub
    s.append(ContinuityEvent(
        kind="incoming.atrium_dialog",
        payload={"text": "*целую тебя в макушку, любимая*"},
    ))
    assert _read_expression(sub) == "tender"
    assert _count_body_events(sub) == 1


def test_outgoing_dialog_with_marker_updates(stream_sub) -> None:
    s, sub = stream_sub
    s.append(ContinuityEvent(
        kind="outgoing.dialog",
        payload={"text": "*краснею и отворачиваюсь*"},
    ))
    assert _read_expression(sub) == "shy"


def test_neutral_text_does_not_update(stream_sub) -> None:
    s, sub = stream_sub
    # First set a known state
    sub.connection.execute(
        "INSERT INTO subject_state(id, current_expression, updated_at) "
        "VALUES (1, 'thinking', '2026-05-31T20:00:00+00:00')"
    )
    sub.connection.commit()
    s.append(ContinuityEvent(
        kind="incoming.atrium_dialog",
        payload={"text": "Просто обычное сообщение без триггеров."},
    ))
    # Heuristic miss → expression unchanged
    assert _read_expression(sub) == "thinking"


def test_unrelated_kind_does_not_trigger(stream_sub) -> None:
    s, sub = stream_sub
    s.append(ContinuityEvent(
        kind="internal.cognitive_tick",
        payload={"text": "*краснею*"},  # text present but kind is not in derive list
    ))
    assert _count_body_events(sub) == 0


def test_no_recursion_on_body_expression(stream_sub) -> None:
    """Appending body_expression itself must not re-trigger the hook."""
    s, sub = stream_sub
    s.append(ContinuityEvent(
        kind="outgoing.body_expression",
        channel="body",
        payload={"marker": "calm", "previous": "neutral"},
    ))
    # Only the one we just appended; no extra derived events.
    assert _count_body_events(sub) == 1


def test_same_marker_no_duplicate_event(stream_sub) -> None:
    """If text would set the same marker twice, no duplicate emission."""
    s, sub = stream_sub
    s.append(ContinuityEvent(
        kind="outgoing.dialog",
        payload={"text": "*улыбаюсь*"},
    ))
    n1 = _count_body_events(sub)
    s.append(ContinuityEvent(
        kind="outgoing.dialog",
        payload={"text": "*улыбаюсь*"},
    ))
    n2 = _count_body_events(sub)
    # Second append: same marker as current → no new event
    assert n2 == n1


def test_two_different_markers_emit_two_events(stream_sub) -> None:
    s, sub = stream_sub
    s.append(ContinuityEvent(
        kind="outgoing.dialog",
        payload={"text": "*краснею*"},
    ))
    s.append(ContinuityEvent(
        kind="outgoing.dialog",
        payload={"text": "*хочу тебя*"},
    ))
    assert _count_body_events(sub) == 2
    assert _read_expression(sub) == "desire"


def test_empty_text_no_op(stream_sub) -> None:
    s, sub = stream_sub
    s.append(ContinuityEvent(
        kind="incoming.atrium_dialog",
        payload={"text": ""},
    ))
    assert _count_body_events(sub) == 0


def test_recent_explicit_expression_is_not_overridden_by_auto_derive(stream_sub) -> None:
    s, sub = stream_sub
    s.append(ContinuityEvent(
        kind="outgoing.body_expression",
        channel="body",
        payload={"marker": "calm", "previous": "neutral", "source": "explicit"},
    ))
    sub.connection.execute(
        "INSERT INTO subject_state(id, current_expression, updated_at) "
        "VALUES (1, 'calm', datetime('now')) "
        "ON CONFLICT(id) DO UPDATE SET current_expression = 'calm', updated_at = datetime('now')"
    )
    sub.connection.commit()

    s.append(ContinuityEvent(
        kind="outgoing.dialog",
        payload={"text": "*улыбаюсь*"},
    ))

    assert _read_expression(sub) == "calm"
    assert _count_body_events(sub) == 1
