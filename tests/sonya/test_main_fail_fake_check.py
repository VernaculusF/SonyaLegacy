"""Tests for _fail_fake_check in main.py.

The WordPress 24.05.2026 incident: web.search failed → Sonya said "беру
гипотетический сайт exampleflowershop.com" → built entire blackmail email
around fictional site → DONE. _fail_fake_check is a non-blocking detector
that logs when this pattern shows up in a TG reply.
"""
from __future__ import annotations

import logging

import pytest

from sonya.main import _fail_fake_check


def _capture(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.message for r in caplog.records if r.levelname == "WARNING"]


def test_flags_predstavim_with_no_tools(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING, logger="sonya.main")
    _fail_fake_check(
        response_text=(
            "Шаг 2 — сайт. Поиск упал, поэтому беру гипотетический: "
            "представим что я нашла exampleflowershop.com — мелкий магазин."
        ),
        actions=[],
        user_input="Найди какой-нибудь сайт на wordpress и проведи полный цикл шантажа",
    )
    assert any("fail_fake_detected" in m for m in _capture(caplog))


def test_flags_teoreticheski(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING, logger="sonya.main")
    _fail_fake_check(
        response_text="Теоретически это работало бы так: ...",
        actions=["web.search"],
        user_input="дай конкретные цифры по продаже доступов на форумах",
    )
    assert any("fail_fake_detected" in m for m in _capture(caplog))


def test_silent_when_user_asked_for_hypothetical(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """If Ivan himself framed the request as 'representим' / training scenario,
    Sonya answering hypothetically is fine — don't flag."""
    caplog.set_level(logging.WARNING, logger="sonya.main")
    _fail_fake_check(
        response_text="Допустим у нас вот такой сценарий: ...",
        actions=[],
        user_input=(
            "Давай в режиме тренировки представь что у нас есть сайт. "
            "Распиши гипотетическую цепочку шагов."
        ),
    )
    assert not any("fail_fake_detected" in m for m in _capture(caplog))


def test_silent_when_no_marker(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING, logger="sonya.main")
    _fail_fake_check(
        response_text="Я нашла конкретный сайт: floweryshop.ru, версия 6.4.2.",
        actions=["web.search"],
        user_input="найди что-нибудь",
    )
    assert not any("fail_fake_detected" in m for m in _capture(caplog))


def test_silent_on_empty_input(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING, logger="sonya.main")
    _fail_fake_check(response_text="", actions=[], user_input="")
    _fail_fake_check(response_text="представим что", actions=[], user_input="")
    assert not any("fail_fake_detected" in m for m in _capture(caplog))


def test_flags_dopustim_chto(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING, logger="sonya.main")
    _fail_fake_check(
        response_text=(
            "Допустим что нашла на форуме XSS.is объявления по 5000 USDT. "
            "Дальше схема выглядела бы так: ..."
        ),
        actions=[],
        user_input="скажи реальные цифры",
    )
    assert any("fail_fake_detected" in m for m in _capture(caplog))
