"""Tests for _inappropriate_delegation_check.

26.05 19:54 case:
  Ivan: "Ты заебешься это делать... Просто напиши скрипт. Если у тебя
   возникают какие-либо проблемы хотя бы пытайся решить их, а не бросай подход."
  Sonya: "Да, скрипт быстрее. Напишу Python-скрипт... Создаю задачу,
   worker подхватит и отпишусь."
  → tasks.create fired, no code.exec / shell.run

Ivan wanted execute-now, got delegate-to-worker. Detector logs warning.
"""
from __future__ import annotations

import logging

import pytest

from sonya.main import _inappropriate_delegation_check


def _capture(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.message for r in caplog.records if r.levelname == "WARNING"]


def test_real_2605_case_fires(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING, logger="sonya.main")
    _inappropriate_delegation_check(
        response_text=(
            "Да, скрипт быстрее. Напишу Python-скрипт для перебора. "
            "Создаю задачу, worker подхватит и отпишусь."
        ),
        actions=["tasks.create some-id"],
        user_input="Просто напиши скрипт. Не бросай подход.",
    )
    assert any("inappropriate_delegation_detected" in m for m in _capture(caplog))


def test_silent_when_code_exec_fired(caplog: pytest.LogCaptureFixture) -> None:
    """Sonya delegated AND executed — fine, the task is just record-keeping."""
    caplog.set_level(logging.WARNING, logger="sonya.main")
    _inappropriate_delegation_check(
        response_text="Создаю задачу для записи + выполняю скрипт сейчас.",
        actions=["code.exec import requests...", "tasks.create x"],
        user_input="напиши скрипт",
    )
    assert not any("inappropriate_delegation_detected" in m for m in _capture(caplog))


def test_silent_when_no_imperative(caplog: pytest.LogCaptureFixture) -> None:
    """User asked a project question, delegation is appropriate."""
    caplog.set_level(logging.WARNING, logger="sonya.main")
    _inappropriate_delegation_check(
        response_text="Создаю задачу, worker подхватит.",
        actions=["tasks.create x"],
        user_input="Можешь как-нибудь поискать слабые wordpress-сайты?",
    )
    assert not any("inappropriate_delegation_detected" in m for m in _capture(caplog))


def test_silent_when_no_delegation_phrase(caplog: pytest.LogCaptureFixture) -> None:
    """Imperative + tasks.create + result reported = appropriate batch."""
    caplog.set_level(logging.WARNING, logger="sonya.main")
    _inappropriate_delegation_check(
        response_text=(
            "Запустила. 3 пробы по mo, 2 по steph — все 403. Sucuri "
            "режет даже форму. Меняю стратегию — добавлю задержки."
        ),
        actions=["code.exec", "tasks.create"],
        user_input="запусти скрипт",
    )
    assert not any("inappropriate_delegation_detected" in m for m in _capture(caplog))


def test_fires_for_screenscript_imperative(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING, logger="sonya.main")
    _inappropriate_delegation_check(
        response_text="Уйду в фон, worker подхватит.",
        actions=["tasks.create x"],
        user_input="Запусти curl на эту ссылку",
    )
    assert any("inappropriate_delegation_detected" in m for m in _capture(caplog))


def test_silent_on_empty_input(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING, logger="sonya.main")
    _inappropriate_delegation_check("", [], "")
    _inappropriate_delegation_check("ok", [], "напиши скрипт")
    assert not any("inappropriate_delegation_detected" in m for m in _capture(caplog))


def test_silent_when_only_chat_tell_ivan(caplog: pytest.LogCaptureFixture) -> None:
    """If she answered with chat.tell_ivan but didn't create a task, that's
    a different pattern (empty promise, caught elsewhere). Not this detector."""
    caplog.set_level(logging.WARNING, logger="sonya.main")
    _inappropriate_delegation_check(
        response_text="Я тебе обещаю что напишу.",
        actions=["chat.tell_ivan"],  # no tasks.create
        user_input="напиши скрипт",
    )
    assert not any("inappropriate_delegation_detected" in m for m in _capture(caplog))
