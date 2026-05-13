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


@pytest.mark.asyncio
async def test_plan_text_action_uses_normal_reply_for_reply_actions(monkeypatch):
    replies = iter(['{"type":"reply","reply_text":"truncated planner text"}', "full normal answer"])

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
    assert action.reply_text == "full normal answer"


@pytest.mark.asyncio
async def test_plan_text_action_uses_normal_reply_for_reply_and_generate_image(monkeypatch):
    replies = iter(
        [
            '{"type":"reply_and_generate_image","reply_text":"truncated planner text","image_prompt":"scene prompt"}',
            "full normal answer",
        ]
    )

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

    assert action.type == "reply_and_generate_image"
    assert action.reply_text == "full normal answer"
    assert action.image_prompt == "scene prompt"


@pytest.mark.asyncio
async def test_plan_text_action_preserves_task_actions(monkeypatch):
    replies = iter(
        [
            """
            {
              "type": "reply_and_create_task",
              "reply_text": "Задачу поставила.",
              "task_payload": {
                "kind": "workspace_analysis",
                "goal": "Проверить структуру workspace",
                "requested_by_principal": "5785127604",
                "origin_channel": "telegram",
                "origin_chat_id": "5785127604",
                "source_message": "проверь папку",
                "context_summary": "Нужно понять структуру",
                "suggested_steps": ["осмотреть корень"],
                "priority": 4,
                "requires_user_followup": false,
                "followup_prompt": ""
              }
            }
            """
        ]
    )

    async def fake_complete_text(provider, model_name, messages):
        return next(replies)

    monkeypatch.setattr("tg_bridge.app.complete_text", fake_complete_text)

    action = await _plan_text_action_with_fallback(
        {"baseUrl": "x", "apiKey": "y"},
        "model",
        {"agents": "", "soul": "", "heartbeat": "", "identity": "", "memoryContext": ""},
        {"messages": []},
        "проверь папку",
    )

    assert action.type == "reply_and_create_task"
    assert action.reply_text == "Задачу поставила."
    assert action.task_payload is not None
    assert action.task_payload.kind == "workspace_analysis"
