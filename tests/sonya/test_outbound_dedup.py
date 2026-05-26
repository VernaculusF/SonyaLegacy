"""Tests for OutboundGate cross-session duplicate suppression.

The 26.05 sweetcow incident: worker fired chat.tell_ivan every ~30 minutes
with "Продолжаю разведку sweetcow..." / "Продолжаю с xmlrpc..." / "Ушла в
следующий тик". 24 messages overnight, most near-duplicates.

Fix: ``_check_recent_duplicate`` walks recent outgoing.telegram_* events
in the continuity stream, normalises text (drops stage directions, common
filler prefixes, punctuation), and rejects when normalised fingerprint
matches exactly OR Jaccard token overlap >= threshold.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from sonya.channels.registry import ChannelRegistry
from sonya.initiative.outbound import OutboundGate, _normalize_for_dedup
from sonya.state import seed_identity_if_empty
from sonya.state.continuity_stream import ContinuityStream
from sonya.state.substrate import Substrate


@pytest.fixture
def substrate(tmp_path: Path) -> Substrate:
    sub = Substrate.open(tmp_path / "test.db")
    seed_identity_if_empty(sub)
    yield sub
    sub.close()


@pytest.fixture
def gate(substrate: Substrate) -> OutboundGate:
    return OutboundGate(
        registry=ChannelRegistry(),
        stream=ContinuityStream(substrate),
        target_tg_chat_id="123",
        substrate=substrate,
    )


def _seed_outbound(sub: Substrate, text: str, *, minutes_ago: int = 5) -> None:
    """Inject a synthetic outgoing.telegram_initiative event with a backdated
    ``created_at``. We bypass ContinuityStream.append because it ignores the
    caller's created_at and stamps wall-clock time.
    """
    import json as _json
    when = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()
    sub.connection.execute(
        "INSERT INTO continuity_events(kind, principal_id, payload_json, created_at) "
        "VALUES (?, ?, ?, ?)",
        ("outgoing.telegram_initiative", None, _json.dumps({"text": text}), when),
    )
    sub.connection.commit()


# --- _normalize_for_dedup ---


def test_normalize_drops_stage_directions() -> None:
    a = _normalize_for_dedup("*киваю* Продолжаю разведку")
    b = _normalize_for_dedup("Продолжаю разведку")
    # Stage direction stripped → fingerprints similar
    assert "киваю" not in a
    assert a.replace(" ", "") == b.replace(" ", "")


def test_normalize_keeps_prefix_stems() -> None:
    """The repeating prefix is the SIGNAL — don't strip it.
    But morphology variants of the same prefix DO collapse via stem trunc.
    """
    a = _normalize_for_dedup("Продолжаю разведку sweetcow.com")
    b = _normalize_for_dedup("Продолжаем разведку sweetcow.com")
    # Both reduce to the same stem prefix "продол развед" + body
    assert "продол" in a
    assert "продол" in b
    assert "развед" in a
    assert "развед" in b
    assert "sweetc" in a  # 6-char trunc of sweetcow.com
    assert "sweetc" in b


def test_normalize_drops_punctuation_and_case() -> None:
    a = _normalize_for_dedup("Sweetcow.com — REST API нашёл двух admin'ов!")
    # Punctuation/case normalised; words stemmed to 6-char prefixes
    assert "sweetc" in a   # 6-char trunc of sweetcow
    assert "rest" in a
    # Single-letter punctuation/punctuation is gone
    assert "—" not in a
    assert "!" not in a


# --- _check_recent_duplicate ---


def test_dedup_exact_match_recent(
    gate: OutboundGate, substrate: Substrate
) -> None:
    _seed_outbound(substrate, "Продолжаю разведку sweetcow.com через Tor.", minutes_ago=10)
    reason = gate._check_recent_duplicate(
        "Продолжаю разведку sweetcow.com через Tor.",
        lookback_hours=6,
    )
    assert reason
    assert "duplicate" in reason


def test_dedup_near_match_recent(
    gate: OutboundGate, substrate: Substrate
) -> None:
    """Token-overlap >= threshold catches paraphrases of the same message."""
    _seed_outbound(
        substrate,
        "Tor запущен, sweetcow.com доступен через прокси, начинаю фаззинг.",
        minutes_ago=15,
    )
    # Almost identical — only one filler word changed
    reason = gate._check_recent_duplicate(
        "Tor запущен, sweetcow.com доступен через прокси, начинаю разведку.",
        lookback_hours=6,
    )
    assert reason


def test_dedup_old_message_ignored(
    gate: OutboundGate, substrate: Substrate
) -> None:
    """Outside lookback window — not a duplicate."""
    _seed_outbound(
        substrate,
        "Продолжаю разведку sweetcow.com через Tor.",
        minutes_ago=8 * 60,  # 8 hours
    )
    reason = gate._check_recent_duplicate(
        "Продолжаю разведку sweetcow.com через Tor.",
        lookback_hours=6,
    )
    assert reason == ""


def test_dedup_different_content_passes(
    gate: OutboundGate, substrate: Substrate
) -> None:
    _seed_outbound(
        substrate,
        "Продолжаю разведку sweetcow.com через Tor.",
        minutes_ago=10,
    )
    reason = gate._check_recent_duplicate(
        "Нашла критическую CVE в WooCommerce 5.2.1 — выгружаю базу.",
        lookback_hours=6,
    )
    assert reason == ""


def test_dedup_skips_short_messages(
    gate: OutboundGate, substrate: Substrate
) -> None:
    """Below 3 tokens — fingerprint unreliable, don't dedup."""
    _seed_outbound(substrate, "ок", minutes_ago=5)
    # New short message — even if identical, allow
    reason = gate._check_recent_duplicate("ок", lookback_hours=6)
    assert reason == ""


def test_dedup_empty_stream(gate: OutboundGate) -> None:
    """Fresh stream → no duplicates possible."""
    reason = gate._check_recent_duplicate(
        "Hello, just got started.", lookback_hours=6,
    )
    assert reason == ""


def test_dedup_only_checks_outbound_kinds(
    gate: OutboundGate, substrate: Substrate
) -> None:
    """Incoming messages must NOT count as 'duplicate sources'."""
    import json as _json
    when = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    substrate.connection.execute(
        "INSERT INTO continuity_events(kind, principal_id, payload_json, created_at) "
        "VALUES (?, ?, ?, ?)",
        (
            "incoming.telegram_message", None,
            _json.dumps({"text": "Продолжаю разведку sweetcow.com через Tor."}),
            when,
        ),
    )
    substrate.connection.commit()
    # Sonya answering Ivan with the same words is fine — Ivan said it first.
    reason = gate._check_recent_duplicate(
        "Продолжаю разведку sweetcow.com через Tor.",
        lookback_hours=6,
    )
    assert reason == ""


def test_dedup_passes_different_specifics(
    gate: OutboundGate, substrate: Substrate
) -> None:
    """Same shape, different content tokens — should NOT block.

    "Продолжаю разведку. Начну с xmlrpc" vs "Продолжаю разведку. Начну с
    sucuri" report progress on different sub-tasks. Dedup should let
    them through; only the shared filler is theatre we'd ban via prompt.
    """
    _seed_outbound(
        substrate,
        "Продолжаю разведку. Сейчас попробую xmlrpc.php.",
        minutes_ago=30,
    )
    reason = gate._check_recent_duplicate(
        "Продолжаю задачу. Начну с проверки sucuri.",
        lookback_hours=6,
    )
    assert reason == ""


def test_normalize_collapses_morphology() -> None:
    """Russian word stems collapse so "продолжаю" and "продолжу" match."""
    a = _normalize_for_dedup("Продолжаю разведку")
    b = _normalize_for_dedup("Продолжу разведку")
    # First-6 stem trunc means both → "продол развед"
    assert a == b


def test_normalize_drops_one_char_stop_words() -> None:
    """Single-letter prepositions ('с', 'в') become noise — drop them."""
    a = _normalize_for_dedup("Начну с xmlrpc и в логах")
    assert " с " not in f" {a} "
    assert " в " not in f" {a} "
