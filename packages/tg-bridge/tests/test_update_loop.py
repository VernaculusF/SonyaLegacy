import json
from pathlib import Path

import pytest

from tg_bridge.update_loop import append_jsonl, poll_once


def test_append_jsonl_appends_single_line(tmp_path: Path):
    path = tmp_path / "raw-updates.jsonl"
    append_jsonl(path, {"hello": "world"})
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0]) == {"hello": "world"}


@pytest.mark.asyncio
async def test_poll_once_advances_offset_and_handles_updates(tmp_path: Path):
    state = {"offset": 10}
    writes = []
    handled = []
    raw_path = tmp_path / "raw-updates.jsonl"

    async def fake_get_updates(token: str, offset: int):
        assert token == "token"
        assert offset == 10
        return [{"update_id": 15, "message": {"text": "hello"}}]

    async def fake_handle_update(cfg, update):
        handled.append(update["update_id"])

    def fake_write_state(new_state):
        writes.append(dict(new_state))

    await poll_once(
        token="token",
        cfg={"channels": {"telegram": {"botToken": "token"}}},
        state=state,
        get_updates=fake_get_updates,
        handle_update=fake_handle_update,
        write_state=fake_write_state,
        raw_updates_path=raw_path,
    )

    assert state["offset"] == 16
    assert writes[-1]["offset"] == 16
    assert handled == [15]

