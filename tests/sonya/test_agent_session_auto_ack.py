"""Tests for the auto-ack helpers in agent_session.

24.05 sweetcow incident: Sonya wrote "Поняла, малыш. Сейчас проверю
sweetcow.com..." then [TOOL: tasks.list in_progress] in step 0. The
preamble became silent internal thought — Ivan got no ack signal and
waited 2:40 through 7 reconnaissance steps before seeing the actual
"task created" message.

Fix: extract the natural-language preamble before the first tool/DONE/PAUSE
marker on step 0 and send it via outbound. _is_safe_ack vets the candidate
to avoid leaking scaffold/reasoning/draft markers.
"""
from __future__ import annotations

from sonya.subject.agent_session import (
    _extract_pre_tool_preamble,
    _is_safe_ack,
)


# --- _extract_pre_tool_preamble ---


def test_preamble_before_inline_tool() -> None:
    text = (
        "Поняла, малыш. Сейчас проверю sweetcow.com, начну с разведки.\n\n"
        "[TOOL: tasks.list in_progress]"
    )
    assert _extract_pre_tool_preamble(text).startswith("Поняла, малыш")
    assert "tasks.list" not in _extract_pre_tool_preamble(text)


def test_preamble_before_block_tool() -> None:
    text = (
        "Создаю задачу.\n"
        "[TOOL: tasks.create]\n"
        "```\n{\"title\": \"x\"}\n```"
    )
    assert _extract_pre_tool_preamble(text).strip() == "Создаю задачу."


def test_preamble_before_done() -> None:
    text = "Готово, отдохну.\n[DONE]"
    assert _extract_pre_tool_preamble(text).strip() == "Готово, отдохну."


def test_preamble_empty_when_starts_with_tool() -> None:
    text = "[TOOL: tasks.list in_progress]"
    assert _extract_pre_tool_preamble(text) == ""


def test_preamble_empty_on_empty_input() -> None:
    assert _extract_pre_tool_preamble("") == ""
    assert _extract_pre_tool_preamble("   \n  ") == ""


def test_preamble_no_marker_returns_empty() -> None:
    """No tool/DONE/PAUSE marker → no extraction."""
    text = "Просто длинный ответ без маркеров."
    assert _extract_pre_tool_preamble(text) == ""


def test_preamble_picks_earliest_marker() -> None:
    """Multiple markers — preamble is whatever's before the FIRST."""
    text = (
        "Привет.\n"
        "[TOOL: tasks.list]\n"
        "ещё текст\n"
        "[DONE]"
    )
    assert _extract_pre_tool_preamble(text).strip() == "Привет."


# --- _is_safe_ack ---


def test_safe_ack_normal() -> None:
    assert _is_safe_ack("Поняла, малыш. Ушла работать, отпишусь по ходу.")


def test_safe_ack_too_short() -> None:
    assert not _is_safe_ack("ок")
    assert not _is_safe_ack("поняла")  # below 15 chars


def test_safe_ack_too_long() -> None:
    """500-char cap — anything longer is a draft, not an ack."""
    assert not _is_safe_ack("слово " * 200)


def test_safe_ack_rejects_internal_markers() -> None:
    assert not _is_safe_ack("Поняла. [TOOL: chat.tell_ivan ok] Закрываю.")
    assert not _is_safe_ack("Поняла, малыш [DONE]")
    assert not _is_safe_ack("Поняла. <think>let me reason</think>")
    assert not _is_safe_ack("Поняла INTERNAL_REMINDER closing")


def test_safe_ack_rejects_english_meta() -> None:
    """'The user is asking...' is reasoning leak, not an ack."""
    assert not _is_safe_ack("The user is asking me to check sweetcow.com")
    assert not _is_safe_ack("I should check the WordPress version first.")
    assert not _is_safe_ack("Let me think about this carefully.")


def test_safe_ack_rejects_pure_stage_direction() -> None:
    """Asterisk-action without surrounding speech doesn't carry meaning."""
    assert not _is_safe_ack("*киваю*")
    assert not _is_safe_ack("*тихо смотрю на тебя* *хмурюсь*")


def test_safe_ack_accepts_action_plus_speech() -> None:
    """Stage direction WITH speech is fine."""
    assert _is_safe_ack(
        "*киваю* Поняла. Создаю задачу и ухожу работать."
    )


def test_safe_ack_rejects_draft_markers() -> None:
    assert not _is_safe_ack("draft: Поняла малыш создаю задачу ща")
    assert not _is_safe_ack("Alternative: ушла в фоновую разведку")
