from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_state(state_path: Path) -> dict[str, Any]:
    try:
        return json.loads(state_path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return {"offset": 0}


def write_state(state_path: Path, value: dict[str, Any]) -> None:
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(f"{json.dumps(value, indent=2)}\n", encoding="utf-8")

