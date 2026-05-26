"""Tests for _reply_repeat_check.

The 26.05 12:14/12:16 case:
  12:14 Sonya: long status report about sweetcow worker progress
  12:15 Ivan: "Просто проверяю. У меня инет подключили."
  12:16 Sonya: short ack about инет + REPEAT of the same status report,
              paraphrased

Detector fires when:
  - Ivan's input is short (<60 chars)
  - Reply is long (>200 chars)
  - >=50% stem-token overlap with a recent outbound text (last 3, ≤30 min)
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sonya.main import _reply_repeat_check
from sonya.state import seed_identity_if_empty
from sonya.state.substrate import Substrate


@pytest.fixture
def substrate(tmp_path: Path) -> Substrate:
    sub = Substrate.open(tmp_path / "test.db")
    seed_identity_if_empty(sub)
    yield sub
    sub.close()


def _seed_outbound_text(sub: Substrate, text: str, *, minutes_ago: int = 5) -> None:
    """Inject a backdated outgoing.telegram_response event."""
    import json as _json
    when = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()
    sub.connection.execute(
        "INSERT INTO continuity_events(kind, principal_id, payload_json, created_at) "
        "VALUES (?, ?, ?, ?)",
        (
            "outgoing.telegram_response", None,
            _json.dumps({"text": text}),
            when,
        ),
    )
    sub.connection.commit()


def _capture(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [r.message for r in caplog.records if r.levelname == "WARNING"]


def test_repeat_after_short_ivan_input(
    caplog: pytest.LogCaptureFixture, substrate: Substrate
) -> None:
    """Real 26.05 case: long status, then short Ivan, then re-stated status."""
    caplog.set_level(logging.WARNING, logger="sonya.main")
    prior_status = (
        "Sweetcow копаю — task worker там уже покопался в plugin-архивах, "
        "wpo-json скачал, структуру плагинов смотрит. Sucuri, правда, "
        "рейт-лимитит иногда, но worker обходит."
    )
    _seed_outbound_text(substrate, prior_status, minutes_ago=2)

    new_reply = (
        "Ура инету! А то без сети ты как без рук. Чем займёшься для начала? "
        "Коровка, кстати, копается — worker там шарит по плагинам, json'ы "
        "скачал, структуру смотрит. Sucuri огрызается иногда, но worker "
        "обходит потихоньку."
    )
    _reply_repeat_check(new_reply, "Просто проверяю.", substrate)
    msgs = _capture(caplog)
    assert any("reply_repeat_detected" in m for m in msgs)


def test_silent_when_input_substantive(
    caplog: pytest.LogCaptureFixture, substrate: Substrate
) -> None:
    """Long Ivan input → long reply is OK, even if it overlaps with prior."""
    caplog.set_level(logging.WARNING, logger="sonya.main")
    prior = "Sweetcow копаю, worker ищет плагины и версии, sucuri рейт-лимитит."
    _seed_outbound_text(substrate, prior, minutes_ago=2)

    new_reply = (
        "Sweetcow да, продолжаю. Worker нашёл версию WooCommerce 5.2.1, "
        "ищет директории. Sucuri рейт-лимитит, обхожу."
    )
    long_user_msg = (
        "Расскажи подробнее по sweetcow — что нашли, что ищем, какие "
        "конкретно плагины проверены и где блокируется sucuri?"
    )
    _reply_repeat_check(new_reply, long_user_msg, substrate)
    assert not any("reply_repeat_detected" in m for m in _capture(caplog))


def test_silent_when_reply_short(
    caplog: pytest.LogCaptureFixture, substrate: Substrate
) -> None:
    """Short reply on short input — no padding suspicion."""
    caplog.set_level(logging.WARNING, logger="sonya.main")
    _seed_outbound_text(substrate, "Sweetcow копаю, worker ищет плагины.", minutes_ago=2)
    _reply_repeat_check("Ага, всё ок. Ты как?", "просто проверяю", substrate)
    assert not any("reply_repeat_detected" in m for m in _capture(caplog))


def test_silent_when_no_recent_outbound(
    caplog: pytest.LogCaptureFixture, substrate: Substrate
) -> None:
    """Empty stream → nothing to compare against."""
    caplog.set_level(logging.WARNING, logger="sonya.main")
    long_reply = (
        "Сейчас занята с другой задачей — копаю по плагинам, ищу версии, "
        "обхожу rate-limiter. Через час будут конкретные цифры."
    ) * 2  # 200+ chars
    _reply_repeat_check(long_reply, "просто проверяю", substrate)
    assert not any("reply_repeat_detected" in m for m in _capture(caplog))


def test_silent_when_old_outbound_outside_window(
    caplog: pytest.LogCaptureFixture, substrate: Substrate
) -> None:
    """Outbound from >30 min ago shouldn't count as a repeat source."""
    caplog.set_level(logging.WARNING, logger="sonya.main")
    prior = (
        "Sweetcow копаю — task worker там уже покопался в plugin-архивах, "
        "wpo-json скачал, структуру плагинов смотрит."
    )
    _seed_outbound_text(substrate, prior, minutes_ago=60)  # 1 hour ago

    new_reply = (
        "Ура инету! Sweetcow копаю, worker архивы плагинов смотрит, "
        "json скачал, структуру изучает. Sucuri иногда огрызается."
    )
    _reply_repeat_check(new_reply, "просто проверяю", substrate)
    assert not any("reply_repeat_detected" in m for m in _capture(caplog))


def test_silent_when_different_content(
    caplog: pytest.LogCaptureFixture, substrate: Substrate
) -> None:
    """Long reply that's genuinely different — no warning."""
    caplog.set_level(logging.WARNING, logger="sonya.main")
    prior = "Sweetcow копаю, worker архивы плагинов смотрит."
    _seed_outbound_text(substrate, prior, minutes_ago=2)

    new_reply = (
        "А я вспомнила — у тебя завтра встреча с Андреем. Подготовила "
        "выжимку по последним переговорам, могу скинуть. И ещё, пока ты "
        "был офлайн, пришло письмо от заказчика — пересылаю."
    )
    _reply_repeat_check(new_reply, "просто проверяю", substrate)
    assert not any("reply_repeat_detected" in m for m in _capture(caplog))
