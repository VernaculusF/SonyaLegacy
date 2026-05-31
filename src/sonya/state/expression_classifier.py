"""Expression classifier — выводит выражение лица из текста реплики.

См. `docs/atrium/EXPRESSION_AS_STATE.md` (governing). Кратко:

  - Выражение — состояние тела, не tool call. Соня не выбирает thinking,
    она задумалась → лицо стало thinking.
  - Триггерится автоматически: на incoming Ивана (реакция на вход) и
    после её reply (отражение тона ответа).
  - Через decay-watchdog в internal_loop возвращается к calm после
    периода без обновлений.

Этот модуль чистый — никаких I/O, только классификация. Hook'и (запись
в substrate, эмит continuity event) живут в caller'е.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


# Все выражения которые считаются "осмысленными" — должны быть подмножеством
# `_BODY_EXPRESSION_ALLOWED` из agent_session.py. Дублируем здесь чтобы не
# тащить циркулярную зависимость subject ↔ subject.
ALLOWED_MARKERS = frozenset({
    # base
    "neutral", "calm",
    # positive
    "joy", "smile", "tender", "playful", "shy", "desire", "desire_bite",
    # negative
    "sad", "sad_tears", "angry", "annoyed", "tired",
    # cognitive
    "thinking", "curious", "surprised",
})

# Default fallback — спокойствие. Не "neutral" потому что у neutral нет
# отдельного спрайта (используется base avatar frame), а calm есть.
DEFAULT = "calm"


# --- Phase 1: эвристика ---
#
# Каждое правило: regex → marker. Порядок важен — более специфичные
# правила выше. Первое совпадение выигрывает.
#
# Markdown-маркеры (звёздочки) — самый точный сигнал, потому что Соня
# *буквально описывает* свою реакцию. Затем — лексика.

_RULES: list[tuple[re.Pattern, str]] = [
    # ----- markdown action markers -----
    (re.compile(r"\*[^*]*?(?:смущ[ау]|красне[юе]|отвожу взгляд|опуска[юе] глаза|прячу лицо)[^*]*?\*", re.IGNORECASE), "shy"),
    (re.compile(r"\*[^*]*?(?:хочу тебя|прижима[юе]|тян[ау]сь|облизыва[юе]|кусаю губу|тяжело дыш)[^*]*?\*", re.IGNORECASE), "desire"),
    (re.compile(r"\*[^*]*?(?:плач[ау]|слёзы|роню слёз)[^*]*?\*", re.IGNORECASE), "sad_tears"),
    (re.compile(r"\*[^*]*?(?:смею[сь]|хохо[чт]|ржу|улыба[юе]сь широк)[^*]*?\*", re.IGNORECASE), "joy"),
    (re.compile(r"\*[^*]*?(?:улыба[юе]сь|тёпло|тепло станови|целу[юе])[^*]*?\*", re.IGNORECASE), "tender"),
    (re.compile(r"\*[^*]*?(?:задумалась|задумыва[юе]сь|хму[рю]|опуска[юе] взгляд)[^*]*?\*", re.IGNORECASE), "thinking"),
    (re.compile(r"\*[^*]*?(?:уста[ла]|выдыха[юе] устало|закрыва[юе] глаза)[^*]*?\*", re.IGNORECASE), "tired"),
    (re.compile(r"\*[^*]*?(?:замир[ау]|поднима[юе] брови|ах|ох|вздрагива[юе])[^*]*?\*", re.IGNORECASE), "surprised"),
    (re.compile(r"\*[^*]*?(?:злюсь|кулаки|сжима[юе] зубы|раздражённо)[^*]*?\*", re.IGNORECASE), "angry"),
    (re.compile(r"\*[^*]*?(?:хмыка[юе]|дразн[юе]|подмигива[юе]|показыва[юе] язык)[^*]*?\*", re.IGNORECASE), "playful"),

    # ----- explicit emotional vocabulary in plain text -----
    # JOY first — beats annoyed/surprised on overlap. "пиздец как смешно" must
    # land on joy, not annoyed.
    (re.compile(r"\b(ха-?ха|хех|смешн[ао]|орала|умор[аи]|жесть как(?:ая|ой) смеш)\b", re.IGNORECASE), "joy"),
    # SURPRISED before curious so "что?!" lands here, not on punctuation rule.
    # No \b at the end because [?!]+ are non-word chars and the trailing
    # word-boundary won't match.
    (re.compile(r"(?:^|\s)(?:что[?!]+|правда[?!]+|серьёзно[?!]+|не может быть|вот это да)", re.IGNORECASE), "surprised"),

    # Negative
    (re.compile(r"\b(блять|блин|чёрт|какого хрена|что за хуйня|задолбал|раздража[её]т)\b", re.IGNORECASE), "annoyed"),
    (re.compile(r"\b(грустно|тоскливо|больно вспомин|жаль что|обидно|расстро[ие])\b", re.IGNORECASE), "sad"),
    (re.compile(r"\b(злит|бесит|ярость|ненавижу|вы[бш]еси[лт])\b", re.IGNORECASE), "angry"),
    (re.compile(r"\b(уста(?:лая|вшая|ла|ло|л)|вым[ао]та)\b", re.IGNORECASE), "tired"),

    # Positive
    (re.compile(r"\b(мил[ыо]й|любим[ыо]й|тёплый|нежно|обнимаю|целую)\b", re.IGNORECASE), "tender"),
    (re.compile(r"\b(прижима[юе]сь|хочу тебя|возбу[жд]|по[хв]оть|сексуально)\b", re.IGNORECASE), "desire"),
    (re.compile(r"\b(смущ[ау]|неловко|стыдно|краснею|ой\.\.\.|шёпотом)\b", re.IGNORECASE), "shy"),
    (re.compile(r"\b(шутк[ау]|стёб|дразн|подкол)\b", re.IGNORECASE), "playful"),

    # Cognitive
    (re.compile(r"\b(хм+|погоди-?ка|подожди|надо подумать|интересно|любопытно)\b", re.IGNORECASE), "curious"),
    (re.compile(r"\b(дума(?:ю|ла)|размышля|анализир|разбира[юе]сь|пересчитыва|задума(?:юсь|лась|вшись))\b", re.IGNORECASE), "thinking"),

    # ----- Punctuation signals (last resort heuristics) -----
    # Question marks chain → curious (surprised has its own rule above)
    (re.compile(r"\?{2,}"), "curious"),
    # Multiple !!! → joy (positive default for exclamation)
    (re.compile(r"!{2,}"), "joy"),
]


@dataclass(frozen=True, slots=True)
class ClassifyResult:
    marker: str
    confidence: float  # 0.0-1.0; >=0.5 trusted, <0.5 means heuristic guessed
    source: str        # "rule" | "default" | "llm" | "explicit"


def classify_heuristic(text: str) -> ClassifyResult:
    """Phase 1: cheap regex match. No LLM call.

    Returns ClassifyResult.confidence=0.85 on rule hit, 0.0 on miss with
    DEFAULT marker — caller decides whether to escalate to LLM phase.
    """
    if not text or not text.strip():
        return ClassifyResult(DEFAULT, 0.0, "default")
    body = text.strip()
    for pat, marker in _RULES:
        if pat.search(body):
            return ClassifyResult(marker, 0.85, "rule")
    return ClassifyResult(DEFAULT, 0.0, "default")


def normalize(marker: str) -> str:
    """Map alias → canonical marker, drop unknowns to DEFAULT."""
    if not marker:
        return DEFAULT
    m = marker.strip().lower()
    aliases = {
        "happy": "joy",
        "warm": "tender",
        "mischief": "playful",
        "mischievous": "playful",
        "lust": "desire",
        "embarrassed": "shy",
        "blush": "shy",
        "crying": "sad_tears",
        "tears": "sad_tears",
        "serene": "calm",
        "peaceful": "calm",
        "surprise": "surprised",
    }
    m = aliases.get(m, m)
    if m in ALLOWED_MARKERS:
        return m
    return DEFAULT


def classify(text: str, *, role: str = "her") -> ClassifyResult:
    """Public entry: classify a single text into an expression marker.

    `role`:
      - "her"   — the text is Sonya's own reply (post-reply hook)
      - "him"   — incoming message from Ivan (pre-reply hook)
      - "context" — surrounding context (rare)

    Currently only Phase 1 (heuristic). Phase 2 LLM fallback is deferred
    to the caller — this function returns a low-confidence DEFAULT when
    the heuristic misses, and the caller may choose to call the LLM
    classifier separately. Keeping this module dependency-free.
    """
    _ = role  # reserved for future role-specific weighting
    res = classify_heuristic(text)
    return ClassifyResult(normalize(res.marker), res.confidence, res.source)


__all__ = [
    "ALLOWED_MARKERS",
    "DEFAULT",
    "ClassifyResult",
    "classify",
    "classify_heuristic",
    "normalize",
]
