from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _session_file(session_dir: Path, chat_id: int) -> Path:
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir / f"{chat_id}.json"


def load_session(session_dir: Path, chat_id: int) -> dict[str, Any]:
    try:
        return json.loads(_session_file(session_dir, chat_id).read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return {"messages": []}


def save_session(session_dir: Path, chat_id: int, session: dict[str, Any]) -> None:
    payload = {"messages": list((session.get("messages") or []))[-20:]}
    _session_file(session_dir, chat_id).write_text(
        f"{json.dumps(payload, indent=2)}\n",
        encoding="utf-8",
    )

