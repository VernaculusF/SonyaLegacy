"""Layer 1 (static_contract) must not feed non-Python files into ast.parse.

The 27.05.10:04 incident: Sonya tried to selfmod-edit
`src/sonya/prompts/channel_task_worker.md`. Layer 1 ran ast.parse on the
markdown body and rejected with "SyntaxError: invalid character '—'
(U+2014)". She kept retrying with em-dashes stripped — same error, because
the source markdown ALREADY contains em-dashes that her edit copied
through. Five proposals all got status=draft because they never cleared
Layer 1.

Fix: gate `ast.parse` on `.py`/`.pyi` extension. For other files (.md,
.json, .yml, prompt fragments), do basic sanity (non-empty, size cap).
"""
from __future__ import annotations

from sonya.selfmod.layers.static_contract import check_static_contract
from sonya.selfmod.proposal import SelfModificationProposal


_FULL = "FULL_CONTENT:\n"


def _make(target: str, content: str) -> SelfModificationProposal:
    return SelfModificationProposal(
        proposal_id="smod-test",
        target_module=target,
        change_summary="test",
        diff_blob=_FULL + content,
    )


# --- markdown / non-Python targets must pass Layer 1 with em-dash etc ---


def test_markdown_with_em_dash_passes() -> None:
    """Em-dash (U+2014) in a markdown prompt must NOT trip ast.parse."""
    md = (
        "# Worker rules\n\n"
        "- Если действие не дало нового результата — смени подход.\n"
        "- Не повторяй один и тот же next_step трижды — это автоматический "
        "stuck-loop детектор → задача уходит в blocked.\n"
    )
    result = check_static_contract(_make(
        "src/sonya/prompts/channel_task_worker.md", md,
    ))
    assert result.passed is True
    assert "non-python" in result.reason.lower()


def test_markdown_empty_content_rejected() -> None:
    result = check_static_contract(_make(
        "src/sonya/prompts/channel_x.md", "   \n\n   ",
    ))
    assert result.passed is False
    assert "empty" in result.reason.lower()


def test_markdown_oversized_rejected() -> None:
    huge = "x" * 500_001
    result = check_static_contract(_make(
        "src/sonya/prompts/channel_x.md", huge,
    ))
    assert result.passed is False
    assert "oversized" in result.reason.lower()


def test_json_config_passes_with_unicode() -> None:
    """Other text formats (yaml, json, toml) also accepted."""
    content = '{"label": "Иван", "icon": "—"}'
    result = check_static_contract(_make(
        "src/sonya/skills/data/x.json", content,
    ))
    assert result.passed is True


# --- python targets still get full ast check ---


def test_python_target_with_syntax_error_rejected() -> None:
    bad = "def foo(:\n    return 1\n"
    result = check_static_contract(_make(
        "src/sonya/tools/example.py", bad,
    ))
    assert result.passed is False
    assert "SyntaxError" in result.reason


def test_python_target_valid_passes() -> None:
    good = "def foo() -> int:\n    return 1\n"
    result = check_static_contract(_make(
        "src/sonya/tools/example_new.py", good,
    ))
    assert result.passed is True
