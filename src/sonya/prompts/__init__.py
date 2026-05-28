"""Prompt loading for Sonya sessions.

All session prompts live as .md files in this directory (or subdirs).
Code loads them at runtime — never hardcoded in Python.
"""
from __future__ import annotations

from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent


def load_prompt(name: str) -> str:
    """Load a prompt file by name (without .md extension).

    Raises FileNotFoundError if not found.
    """
    path = _PROMPTS_DIR / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"Prompt not found: {path}")
    return path.read_text(encoding="utf-8")


def load_session_suffix(channel: str = "telegram") -> str:
    """Load the combined session suffix: general rules + channel-specific overlay.

    Returns ``session_general.md`` + ``channel_{channel}.md`` concatenated.

    Per cognition/COGNITION.md: Sonya is one subject, channels are
    surfaces. The general rules (anti-fail-fake / anti-sycophancy / anti-
    hallucination / 5-step retry escalation) apply to ALL surfaces, not only
    Telegram. Channel-specific files only add adapter chrome (formatting,
    prompt-echo patterns, etc.).

    Recognised channels:
      - ``telegram`` — outward-facing TG userbot turn
      - ``internal_active`` — active session (every 2h, with tools, internal)
      - ``task_worker`` — short worker tick (5 steps, 60s, advances Ivan-task)

    Idle thinking has no tools and uses a separate inline prompt in main.py.
    """
    parts = []
    general = _PROMPTS_DIR / "session_general.md"
    if general.exists():
        parts.append(general.read_text(encoding="utf-8"))
    channel_file = _PROMPTS_DIR / f"channel_{channel}.md"
    if channel_file.exists():
        parts.append(channel_file.read_text(encoding="utf-8"))
    return "\n\n".join(parts)
