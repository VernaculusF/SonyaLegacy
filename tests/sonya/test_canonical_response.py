from __future__ import annotations

import pytest

from sonya.state.canonical_response import CanonicalResponse, ResponseKind


def test_response_kind_has_all_11_kinds() -> None:
    expected = {
        "reply",
        "task_created",
        "task_update",
        "task_result",
        "image_generated",
        "clarification",
        "limitation",
        "silence",
        "initiative_proposal",
        "self_observation",
        "internal_reflection",
    }
    actual = {k.value for k in ResponseKind}
    assert actual == expected


def test_canonical_response_round_trip() -> None:
    r = CanonicalResponse(
        kind=ResponseKind.REPLY,
        text="hello",
        principal_id="ivan",
        task_ref="task-123",
        attachments=("img.png",),
        metadata={"source": "planner"},
    )
    assert r.kind is ResponseKind.REPLY
    assert r.text == "hello"
    assert r.principal_id == "ivan"
    assert r.task_ref == "task-123"
    assert r.attachments == ("img.png",)
    assert r.metadata == {"source": "planner"}


def test_canonical_response_defaults() -> None:
    r = CanonicalResponse(kind=ResponseKind.SILENCE)
    assert r.text == ""
    assert r.principal_id is None
    assert r.task_ref == ""
    assert r.attachments == ()
    assert r.metadata == {}
    assert r.created_at != ""


def test_canonical_response_is_frozen() -> None:
    r = CanonicalResponse(kind=ResponseKind.REPLY, text="x")
    with pytest.raises(Exception):
        r.text = "y"  # type: ignore[misc]


def test_all_kinds_are_valid_enum_members() -> None:
    for kind in ResponseKind:
        r = CanonicalResponse(kind=kind)
        assert r.kind is kind


def test_created_at_auto_fills_iso() -> None:
    r = CanonicalResponse(kind=ResponseKind.INTERNAL_REFLECTION)
    assert "T" in r.created_at
    assert "+" in r.created_at or "Z" in r.created_at
