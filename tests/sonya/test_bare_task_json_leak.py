"""Tests for the bare-task-JSON leak fix.

24.05 incident: model wrote
    "Продолжу в фоне — создаю задачу.{\"title\": \"...\", \"plan_steps\": [...]}"
without a [TOOL: tasks.create] wrapper. Two problems:
  1. Ivan saw raw JSON in TG (UX leak)
  2. Task was NOT actually created (dispatcher needs the marker)

Fix layers:
- channel_session._strip_bare_task_json: scrubs the JSON from user-facing text
- main._bare_task_json_check: logs a warning so we see the tool-call failure
"""
from __future__ import annotations

import logging

import pytest

from sonya.main import _bare_task_json_check
from sonya.subject.channel_session import _strip_bare_task_json, _scrub


# --- _strip_bare_task_json ---


def test_strip_bare_task_json_removes_unwrapped_arg() -> None:
    text = (
        "Киваю. Продолжу в фоне — создаю задачу."
        '{"title": "Сканирование 9 сайтов", "plan_steps": ["a", "b"]}'
    )
    result = _strip_bare_task_json(text)
    assert "title" not in result
    assert "plan_steps" not in result
    assert "Продолжу в фоне" in result


def test_strip_bare_task_json_preserves_non_task_json() -> None:
    """Other JSON the user/model produces (not a task arg) stays."""
    text = 'Вот данные: {"name": "Ivan", "age": 32}. Конец.'
    result = _strip_bare_task_json(text)
    assert "name" in result
    assert "age" in result


def test_strip_bare_task_json_handles_nested_braces() -> None:
    text = (
        'Продолжу. {"title": "x", "plan_steps": ["a"], "meta": {"sub": 1}}. '
        "Готово."
    )
    result = _strip_bare_task_json(text)
    assert "title" not in result
    assert "meta" not in result
    assert "Готово" in result


def test_strip_bare_task_json_handles_strings_with_braces() -> None:
    """Brace inside string literal must not mis-balance the parser."""
    text = '{"title": "func {} works", "plan_steps": ["a"]}'
    result = _strip_bare_task_json(text)
    assert "title" not in result
    assert result.strip() == ""


def test_strip_bare_task_json_no_op_without_marker() -> None:
    text = "Обычный ответ без JSON."
    assert _strip_bare_task_json(text) == text


def test_scrub_removes_bare_task_json_e2e() -> None:
    """Full _scrub pipeline catches the 24.05 leak."""
    raw = (
        "*Киваю, быстро фиксирую результат.* WooCommerce нет, но WordPress есть. "
        "Продолжу в фоне — создаю задачу."
        '{"title": "Сканирование 9 сайтов", '
        '"description": "Найдено 9 живых сайтов малого бизнеса.", '
        '"plan_steps": ["шаг 1", "шаг 2"], "notify_mode": "progress"}'
    )
    cleaned = _scrub(raw)
    assert "title" not in cleaned
    assert "plan_steps" not in cleaned
    # Natural language survives
    assert "WordPress есть" in cleaned
    assert "Продолжу в фоне" in cleaned


# --- _bare_task_json_check ---


def _capture(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.message for r in caplog.records if r.levelname == "WARNING"]


def test_bare_task_json_check_fires_when_no_tool_call(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger="sonya.main")
    _bare_task_json_check(
        raw_response=(
            'Создаю задачу.{"title": "x", "plan_steps": ["a"]}'
        ),
        actions=["web.search"],  # no tasks.create
        user_input="продолжай",
    )
    msgs = _capture(caplog)
    assert any("bare_task_json_leak_detected" in m for m in msgs)


def test_bare_task_json_check_softer_when_tool_did_fire(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """If tasks.create did fire, the JSON is just an echo — still log but
    severity downgraded."""
    caplog.set_level(logging.WARNING, logger="sonya.main")
    _bare_task_json_check(
        raw_response=(
            'Создала задачу: {"title": "x", "plan_steps": ["a"]}. Готово.'
        ),
        actions=["tasks.create some-id"],
        user_input="продолжай",
    )
    # Still fires (echo is leaky), but severity field is "soft"
    rec = next(
        (r for r in caplog.records
         if r.levelname == "WARNING" and "bare_task_json" in r.message),
        None,
    )
    assert rec is not None
    assert rec.severity == "soft"


def test_bare_task_json_check_silent_without_marker(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger="sonya.main")
    _bare_task_json_check(
        raw_response="Обычный ответ без JSON.",
        actions=[],
        user_input="hi",
    )
    assert not any("bare_task_json" in m for m in _capture(caplog))


def test_bare_task_json_check_silent_on_unrelated_json(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Other JSON shapes (no title+plan_steps) shouldn't fire."""
    caplog.set_level(logging.WARNING, logger="sonya.main")
    _bare_task_json_check(
        raw_response='Вот данные: {"name": "Ivan", "age": 32}',
        actions=[],
        user_input="hi",
    )
    assert not any("bare_task_json" in m for m in _capture(caplog))
