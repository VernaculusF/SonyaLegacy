from pathlib import Path

import pytest

from tg_bridge.app import _plan_text_action_with_fallback, create_openclaw_app


def test_create_openclaw_app_uses_openclaw_host():
    app = create_openclaw_app(Path(r"C:\Users\Jester\.openclaw"))
    assert app.host.config_path.name == "openclaw.json"


@pytest.mark.asyncio
async def test_plan_text_action_falls_back_to_normal_reply_when_planner_returns_empty(monkeypatch):
    replies = iter(["", "normal answer"])

    async def fake_complete_text(provider, model_name, messages):
        return next(replies)

    monkeypatch.setattr("tg_bridge.app.complete_text", fake_complete_text)

    action = await _plan_text_action_with_fallback(
        {"baseUrl": "x", "apiKey": "y"},
        "model",
        {"agents": "", "soul": "", "heartbeat": "", "identity": "", "memoryContext": ""},
        {"messages": []},
        "hello",
    )

    assert action.type == "reply"
    assert action.reply_text == "normal answer"
