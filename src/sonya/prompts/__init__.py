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

    Returns general_session.md + channel_{channel}.md concatenated.
    """
    parts = []
    general = _PROMPTS_DIR / "session_general.md"
    if general.exists():
        parts.append(general.read_text(encoding="utf-8"))
    channel_file = _PROMPTS_DIR / f"channel_{channel}.md"
    if channel_file.exists():
        parts.append(channel_file.read_text(encoding="utf-8"))
    return "\n\n".join(parts)
