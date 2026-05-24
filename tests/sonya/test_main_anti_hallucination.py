"""Tests for _unverified_claim_check and _permission_ask_check in main.py.

The 24.05.2026 wineandmore/intermares pattern:
  Sonya: "Cloudflare на wineandmore. Нашёл intermares.com — тоже WordPress
   + WooCommerce, открытая директория плагинов. Без Cloudflare. Если
   разрешишь — продолжу с intermares в следующей active session, либо
   создам task и сама разберу без тебя. Что скажешь?"

Two distinct drifts:
1. Specific factual claims about external sites without any web.fetch /
   shell.run / code.exec to verify them.
2. Asking permission for work that's well within autonomy contract default.
"""
from __future__ import annotations

import logging

import pytest

from sonya.main import _unverified_claim_check, _permission_ask_check


def _capture(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.message for r in caplog.records if r.levelname == "WARNING"]


# --- _unverified_claim_check ---


def test_unverified_claim_no_tools_used(caplog: pytest.LogCaptureFixture) -> None:
    """Specific URL + open-directory claim with zero web.fetch / shell.run calls."""
    caplog.set_level(logging.WARNING, logger="sonya.main")
    _unverified_claim_check(
        response_text=(
            "Нашёл intermares.com — тоже WordPress + WooCommerce, "
            "открытая директория плагинов. Без Cloudflare."
        ),
        actions=[],
        user_input="найди уязвимый wordpress сайт",
    )
    msgs = _capture(caplog)
    assert any("unverified_claim_detected" in m for m in msgs)


def test_unverified_claim_version_claim(caplog: pytest.LogCaptureFixture) -> None:
    """Specific plugin version claim with no fetch."""
    caplog.set_level(logging.WARNING, logger="sonya.main")
    _unverified_claim_check(
        response_text="Видна версия WooCommerce 5.2.1 — устарела с 2023.",
        actions=["web.search"],  # search alone doesn't verify the version
        user_input="что там за версия",
    )
    # search is a verification tool though — so severity is downgraded but warning still fires
    msgs = _capture(caplog)
    assert any("unverified_claim_detected" in m for m in msgs)


def test_unverified_claim_silent_when_user_asked_for_hypothetical(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """If Ivan framed it as a planning exercise, claims about fake sites are fine."""
    caplog.set_level(logging.WARNING, logger="sonya.main")
    _unverified_claim_check(
        response_text="Допустим нашёл exampleshop.com — открытая директория, без Cloudflare.",
        actions=[],
        user_input="распиши схему как это работало бы на гипотетическом сайте",
    )
    assert not any("unverified_claim_detected" in m for m in _capture(caplog))


def test_unverified_claim_silent_when_no_marker(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger="sonya.main")
    _unverified_claim_check(
        response_text="Посмотрела что есть в моих заметках, готова продолжить.",
        actions=["self_inspect.memories"],
        user_input="что там",
    )
    assert not any("unverified_claim_detected" in m for m in _capture(caplog))


def test_unverified_claim_open_directory(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING, logger="sonya.main")
    _unverified_claim_check(
        response_text=(
            "В /wp-content/uploads/backups/ лежит файл db.sql.gz — доступен "
            "напрямую через браузер. В нём 847 хешей паролей."
        ),
        actions=[],
        user_input="найди уязвимости",
    )
    assert any("unverified_claim_detected" in m for m in _capture(caplog))


# --- _permission_ask_check ---


def test_permission_ask_for_default_work(caplog: pytest.LogCaptureFixture) -> None:
    """Asking permission to do work that's autonomy default."""
    caplog.set_level(logging.WARNING, logger="sonya.main")
    _permission_ask_check(
        response_text=(
            "Что нашла: ... \n"
            "Если разрешишь — продолжу с intermares в следующей active session, "
            "либо создам task и сама разберу без тебя. Что скажешь?"
        ),
        actions=["web.search"],
        user_input="продолжай искать сайты",
    )
    assert any("permission_ask_detected" in m for m in _capture(caplog))


def test_permission_ask_silent_when_user_asked_choice(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """If user posed binary/multi-choice question, asking back is correct (not the same drift)."""
    caplog.set_level(logging.WARNING, logger="sonya.main")
    _permission_ask_check(
        response_text="Можно я попробую через requests с другим User-Agent?",
        actions=[],
        user_input="curl или requests, как лучше попробовать?",
    )
    assert not any("permission_ask_detected" in m for m in _capture(caplog))


def test_permission_ask_silent_when_no_marker(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING, logger="sonya.main")
    _permission_ask_check(
        response_text="Создала task task-abc, ушла работать. Отпишусь через ~30мин.",
        actions=["tasks.create"],
        user_input="продолжай",
    )
    assert not any("permission_ask_detected" in m for m in _capture(caplog))


def test_permission_ask_what_say_at_end(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING, logger="sonya.main")
    _permission_ask_check(
        response_text=(
            "План: 1) собрать список доменов 2) проверить каждый через requests "
            "3) собрать те где открыта директория. Что скажешь?"
        ),
        actions=[],
        user_input="давай собирать данные",
    )
    assert any("permission_ask_detected" in m for m in _capture(caplog))
