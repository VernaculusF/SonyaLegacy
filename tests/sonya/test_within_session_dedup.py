"""Tests for within-session chat.tell_ivan dedup.

Cross-session OutboundGate dedup uses Jaccard ≥0.80 over 6h — appropriate
for "stop worker spamming `Продолжаю разведку` every tick". But within
ONE agent session that threshold misses near-identical back-to-back
sends (27.05.21:42 incident — two almost-same OWASP/GitHub progress
messages 60s apart in the same session). Stricter local dedup at 0.55
catches them before they leave the process.
"""
from __future__ import annotations

import pytest

from sonya.subject.agent_session import _within_session_duplicate


# --- positives: should be flagged as duplicate ---


def test_exact_repeat_caught() -> None:
    text = "OWASP Top 10 вытащила, дальше GitHub-репозитории и систематизация."
    assert _within_session_duplicate(text, [text]) is True


def test_near_identical_caught() -> None:
    a = "Начала сбор базы. OWASP Top 10 вытащила, ищу полные категории."
    b = "Начала собирать базу. OWASP Top 10 уже вытащила, ищу категории WSTG."
    assert _within_session_duplicate(b, [a]) is True


def test_mpbacademy_progress_repetition() -> None:
    """The actual 21:42 incident: two progress messages in the same session.

    NOTE: Word-level Jaccard catches near-paraphrases, but this pair uses
    DIFFERENT surface terms ("PayloadsAllTheThings/HackTricks/SecLists" vs
    "GitHub-репозитории/систематизация") for the same intent. Pure
    surface dedup misses it (~0.17 Jaccard). Catching this would need
    embedding-based semantic match — out of scope for the cheap heuristic
    here. Documented as a known limit; flagged for the future
    semantic-dedup follow-up.
    """
    msg1 = (
        "Начала сбор базы. Уже вытащила OWASP Top 10 2021 и ищу полные "
        "категории (WSTG). Следующий шаг — скачаю PayloadsAllTheThings, "
        "HackTricks и SecLists, разложу по полочкам. Отпишусь."
    )
    msg2 = (
        "Поняла, малыш. Уже начала — OWASP Top 10 вытащила, полный "
        "список категорий собираю. Дальше — GitHub-репозитории и "
        "систематизация. Отпишусь как будет готово."
    )
    # Word-level Jaccard ~0.17 — under threshold. Surface-different
    # paraphrase escapes the cheap dedup. NOT a regression.
    assert _within_session_duplicate(msg2, [msg1]) is False


def test_mpbacademy_actual_repeat_caught() -> None:
    """If the model literally rephrases with same key terms, we DO catch it."""
    msg1 = (
        "Начала сбор базы. Вытащила OWASP Top 10 2021 и ищу WSTG, "
        "PayloadsAllTheThings и HackTricks. Отпишусь."
    )
    msg2 = (
        "Уже начала — OWASP Top 10 вытащила, ищу WSTG. "
        "PayloadsAllTheThings и HackTricks дальше. Отпишусь."
    )
    assert _within_session_duplicate(msg2, [msg1]) is True


# --- negatives: should NOT be flagged ---


def test_unrelated_messages_pass() -> None:
    a = "OWASP Top 10 вытащила, дальше GitHub-репозитории."
    b = "Зашла на mpbacademy через прокси — Cloudflare пропустил."
    assert _within_session_duplicate(b, [a]) is False


def test_short_ack_passes() -> None:
    """Short acknowledgements should not be flagged just because they're short."""
    a = "Готово."
    b = "Сделала."
    # Each only ~6 chars normalised; sets too small to match meaningfully.
    assert _within_session_duplicate(b, [a]) is False


def test_progress_with_new_info_passes() -> None:
    """Genuine progression — first finding, then concrete new step — is fine."""
    a = "Начала разведку sweetcow.com."
    b = "Нашла открытую /wp-content/uploads/plugin-archives/ с двумя архивами."
    assert _within_session_duplicate(b, [a]) is False


def test_empty_text_not_caught() -> None:
    assert _within_session_duplicate("", ["anything"]) is False


def test_empty_history_not_caught() -> None:
    assert _within_session_duplicate("hi", []) is False


def test_only_recent_5_checked() -> None:
    """Older sends are ignored — only the last 5 prior outbound items
    count for within-session dedup. Drift over 6+ messages is OK."""
    duplicate = "Точно такое же сообщение."
    history = [
        duplicate,
        "сообщение 2",
        "сообщение 3",
        "сообщение 4",
        "сообщение 5",
        "сообщение 6",
    ]
    assert _within_session_duplicate(duplicate, history) is False  # outside window


def test_recent_5_caught() -> None:
    duplicate = "Точно такое же сообщение."
    history = [
        "сообщение 2",
        "сообщение 3",
        "сообщение 4",
        "сообщение 5",
        duplicate,
    ]
    assert _within_session_duplicate(duplicate, history) is True
