"""Tests for expression_classifier — auto-derive выражения из текста."""
from __future__ import annotations

import pytest

from sonya.state.expression_classifier import (
    ALLOWED_MARKERS,
    DEFAULT,
    classify,
    classify_heuristic,
    normalize,
)


def test_default_when_empty() -> None:
    res = classify("")
    assert res.marker == DEFAULT
    assert res.confidence == 0.0


def test_default_when_no_signal() -> None:
    res = classify("Просто обычное предложение без эмоциональной окраски тут.")
    assert res.marker == DEFAULT
    assert res.confidence < 0.5


@pytest.mark.parametrize("text,expected", [
    ("*краснею и отвожу взгляд*", "shy"),
    ("ой... мне неловко", "shy"),
    ("*хочу тебя*", "desire"),
    ("*прижимаюсь, тяжело дышу*", "desire"),
    ("*кусаю губу*", "desire"),
    ("ха-ха, ну ты даёшь", "joy"),
    ("это пиздец как смешно", "joy"),
    ("любимый мой, обнимаю тебя", "tender"),
    ("блять, как же бесит", "annoyed"),
    ("грустно, что так вышло", "sad"),
    ("*плачу, роняю слёзы*", "sad_tears"),
    ("уставшая я какая-то сегодня", "tired"),
    ("хм, надо подумать", "curious"),
    ("задумалась над этим", "thinking"),
    ("что?! правда?!", "surprised"),
    ("вот это да!! не ожидала", "surprised"),  # "вот это да" rule trumps the !! → joy fallback
    ("ого!! правда круто", "joy"),  # plain !! with no surprise lexicon falls to joy
    ("*хмыкаю и подмигиваю*", "playful"),
    ("стёб засчитан", "playful"),
])
def test_rules_hit(text: str, expected: str) -> None:
    res = classify(text)
    assert res.marker == expected, f"{text!r} expected {expected}, got {res.marker}"
    assert res.confidence >= 0.5


def test_normalize_aliases() -> None:
    assert normalize("happy") == "joy"
    assert normalize("blush") == "shy"
    assert normalize("warm") == "tender"
    assert normalize("crying") == "sad_tears"
    assert normalize("surprise") == "surprised"


def test_normalize_unknown_falls_back() -> None:
    assert normalize("rainbow") == DEFAULT
    assert normalize("") == DEFAULT


def test_all_rules_produce_allowed_markers() -> None:
    """Every regex rule must map to a marker we actually have a sprite for."""
    cases = [
        "*смущаюсь*", "*краснею*", "*хочу тебя*",
        "ха-ха", "блять как бесит", "*плачу*",
        "хм, не уверена", "что?!",
    ]
    for text in cases:
        res = classify(text)
        assert res.marker in ALLOWED_MARKERS


def test_role_does_not_affect_phase1() -> None:
    """Phase 1 heuristic ignores role; Phase 2 LLM (future) may use it."""
    text = "*улыбаюсь*"
    assert classify(text, role="her").marker == "tender"
    assert classify(text, role="him").marker == "tender"
