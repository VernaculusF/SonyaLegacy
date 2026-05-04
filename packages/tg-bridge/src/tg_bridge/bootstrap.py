from __future__ import annotations

from pathlib import Path
from typing import Callable

from tg_bridge.adapters.openclaw import OpenClawHost


Runner = Callable[[Path, list[str]], dict]


def _read_optional_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig").strip()
    except FileNotFoundError:
        return ""


def load_bootstrap_context(host: OpenClawHost, runner: Runner) -> dict[str, str]:
    context = runner(host.context_loader_path, ["full", "7"])
    return {
        "agents": _read_optional_text(host.agents_path),
        "soul": _read_optional_text(host.soul_path),
        "heartbeat": _read_optional_text(host.heartbeat_path),
        "identity": _read_optional_text(host.identity_path),
        "memoryContext": str(context.get("stdout") or "").strip(),
    }

