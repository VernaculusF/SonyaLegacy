from pathlib import Path

from telegram_userbot.sessions import load_session, save_session
from telegram_userbot.state import read_state, write_state


def test_state_round_trip(tmp_path: Path):
    state_path = tmp_path / "state.json"
    write_state(state_path, {"offset": 123})
    assert read_state(state_path)["offset"] == 123


def test_session_is_truncated_to_last_20_messages(tmp_path: Path):
    session_dir = tmp_path / "sessions"
    payload = {"messages": [{"role": "user", "content": str(i)} for i in range(30)]}
    save_session(session_dir, 555, payload)
    loaded = load_session(session_dir, 555)
    assert len(loaded["messages"]) == 20
    assert loaded["messages"][0]["content"] == "10"
