from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False) + "\n")


async def poll_once(
    *,
    token: str,
    cfg: dict[str, Any],
    state: dict[str, Any],
    get_updates: Callable[[str, int], Awaitable[list[dict[str, Any]]]],
    handle_update: Callable[[dict[str, Any], dict[str, Any]], Awaitable[None]],
    write_state: Callable[[dict[str, Any]], None],
    raw_updates_path: Path,
) -> None:
    updates = await get_updates(token, int(state.get("offset", 0)))
    for update in updates:
        append_jsonl(
            raw_updates_path,
            {
                "received_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "update": update,
            },
        )
        state["offset"] = int(update["update_id"]) + 1
        write_state(state)
        await handle_update(cfg, update)
