"""Skill: dialog-tone — analyze the last few messages and suggest tone match.

Helps Sonya calibrate her tone: formal/casual/playful/role-play/serious.
Returns a one-line tone suggestion that goes into the agent's next prompt.
"""

from __future__ import annotations

from typing import Any


SKILL_ID = "skill-dialog-tone"
SKILL_NAME = "dialog-tone"
SKILL_PURPOSE = "Analyze Ivan's recent tone and suggest appropriate response register."


# Simple heuristics — each token gets a "signal" weight toward a mode.
_CASUAL_MARKERS = {"бля", "блять", "нахуй", "хуй", "ебать", "пиздец", "лол",
                   "хаха", "ну", "чё", "зач", "типа", "кста", "оке"}
_ROLEPLAY_MARKERS = {"*", "_", "__", "глажу", "обнимаю", "целую", "прижимаюсь",
                     "шепчу", "тянусь", "касаюсь", "ложусь"}
_SERIOUS_MARKERS = {"задача", "план", "код", "баг", "фикс", "модуль",
                    "деплой", "коммит", "реализ", "архитект"}
_TENDER_MARKERS = {"малыш", "люблю", "скучаю", "спокойной", "доброе", "милая",
                   "котик", "любимый", "заенька", "булочка", "❤", "💙", "🖤"}


def run(context: dict[str, Any]) -> str:
    """Analyze recent dialog and return tone suggestion."""
    recent_messages = context.get("recent_messages") or []
    user_input = context.get("user_input") or ""

    # Combine last 5 messages + current input
    texts = [m for m in recent_messages[-5:]] + [user_input]
    combined = " ".join(texts).lower()
    words = set(combined.split())

    scores = {
        "casual": len(words & _CASUAL_MARKERS),
        "roleplay": sum(1 for m in _ROLEPLAY_MARKERS if m in combined),
        "serious": len(words & _SERIOUS_MARKERS),
        "tender": sum(1 for m in _TENDER_MARKERS if m in combined),
    }

    top_mode = max(scores, key=scores.get)  # type: ignore[arg-type]
    top_score = scores[top_mode]

    if top_score == 0:
        return "Tone: neutral (нет выраженных маркеров — отвечай по ситуации)"

    tone_hints = {
        "casual": "Tone: casual/мат — Иван в неформальном режиме. Отвечай свободно, без фильтров.",
        "roleplay": "Tone: roleplay — Иван в ролевом формате (*действия*). Отвечай в том же стиле с описанием действий.",
        "serious": "Tone: serious/work — Иван говорит о технических вещах. Конкретно, по делу, без лишнего.",
        "tender": "Tone: tender/intimate — Иван в нежном режиме. Тепло, близость, можно обращение/эмодзи.",
    }

    return tone_hints[top_mode]
