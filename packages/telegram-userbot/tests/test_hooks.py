from pathlib import Path

from telegram_userbot.hooks import build_hook_env


def test_build_hook_env_sets_expected_openclaw_variables(tmp_path: Path):
    env = build_hook_env(tmp_path, "telegram-1", "hello", "answer")
    assert env["OPENCLAW_WORKSPACE"] == str(tmp_path)
    assert env["OPENCLAW_SESSION_ID"] == "telegram-1"
    assert env["OPENCLAW_LAST_USER_MSG"] == "hello"
    assert env["OPENCLAW_LAST_ASSISTANT_MSG"] == "answer"
