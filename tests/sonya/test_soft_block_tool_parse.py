"""Soft-block tool parser — recovers `[TOOL: chat.dialog]\n<text>` form.

Regression for the 30.05 empty-arg-chat-dialog incident: model wrote
    [TOOL: chat.dialog]
    Привет, малыш. Я здесь.
which the inline parser saw as `[TOOL: chat.dialog]` (no arg) → tool fired
with empty text. Ivan got nothing.

Soft-block recovery applies only to plain-text tools (chat.*, mind.thought,
mind.focus, body.expression, voice.speak) — anywhere else the inline form
must use brackets/JSON.
"""
from __future__ import annotations

from sonya.subject.agent_session import _extract_tool_call


def test_soft_block_recovers_chat_dialog_text():
    response = (
        "Думаю секунду.\n"
        "[TOOL: chat.dialog]\n"
        "Привет, малыш. Я здесь.\n"
    )
    out = _extract_tool_call(response)
    assert out is not None
    name, arg = out
    assert name == "chat.dialog"
    assert arg.strip() == "Привет, малыш. Я здесь."


def test_soft_block_stops_at_done_marker():
    response = (
        "[TOOL: chat.dialog]\n"
        "Спасибо, я слышу тебя.\n"
        "[DONE]\n"
    )
    out = _extract_tool_call(response)
    assert out is not None
    name, arg = out
    assert name == "chat.dialog"
    assert "[DONE]" not in arg
    assert "слышу тебя" in arg


def test_soft_block_only_for_text_tools():
    """For non-text tools the parser does NOT recover from missing args —
    we'd rather see [ERROR] than misparse."""
    response = (
        "[TOOL: filesystem.list]\n"
        "/some/path\n"
        "more text that probably isn't an argument\n"
    )
    out = _extract_tool_call(response)
    # Inline form was empty → soft-block fall through. filesystem.list is
    # NOT in _SOFT_BLOCK_TEXT_TOOLS so soft-block returns None. The
    # final fallback to _TOOL_INLINE_RE matches and returns empty arg.
    assert out is not None
    name, arg = out
    assert name == "filesystem.list"
    assert arg == ""  # NOT a multi-line arg


def test_inline_form_still_wins():
    """When inline form HAS an arg, soft-block doesn't override it."""
    response = (
        "[TOOL: chat.dialog Привет]\n"
        "lots of other text\n"
    )
    out = _extract_tool_call(response)
    assert out is not None
    name, arg = out
    assert name == "chat.dialog"
    assert arg == "Привет"


def test_block_form_with_fence_still_works():
    """Original code-fence block form remains supported."""
    response = (
        "[TOOL: code.exec]\n"
        "```python\n"
        "print('hi')\n"
        "```\n"
    )
    out = _extract_tool_call(response)
    assert out is not None
    name, arg = out
    assert name == "code.exec"
    assert "print('hi')" in arg


def test_soft_block_mind_thought():
    response = (
        "[TOOL: mind.thought]\n"
        "Странно как затягивает этот код.\n"
    )
    out = _extract_tool_call(response)
    assert out is not None
    assert out[0] == "mind.thought"
    assert "затягивает" in out[1]
