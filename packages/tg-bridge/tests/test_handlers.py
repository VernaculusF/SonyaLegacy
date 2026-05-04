import json
from pathlib import Path

import pytest

from tg_bridge.actions import RuntimeAction
from tg_bridge.handlers import HandlerServices, handle_update, should_allow_sender
from tg_bridge.media import TelegramInput


def test_should_allow_sender_checks_allowlist():
    allowed = {"5785127604"}
    assert should_allow_sender(allowed, "5785127604", "5785127604") is True
    assert should_allow_sender(allowed, "123", "456") is False


@pytest.mark.asyncio
async def test_handle_update_replies_to_start():
    sent_messages = []

    async def fake_send_message(token, chat_id, text):
        sent_messages.append((token, chat_id, text))

    services = HandlerServices(
        extract_input=lambda update: TelegramInput(
            message=update["message"],
            chat_id=5785127604,
            from_id=5785127604,
            text="/start",
            prompt_text="/start",
            attachments=[],
            has_image=False,
            mode="text",
        ),
        send_message=fake_send_message,
    )

    await handle_update(
        {"channels": {"telegram": {"botToken": "token", "allowFrom": ["5785127604"]}}},
        {"message": {"text": "/start"}},
        services=services,
    )

    assert sent_messages == [("token", 5785127604, "OpenClaw bridge online.")]


@pytest.mark.asyncio
async def test_handle_update_text_path_sends_answer_and_runs_hook():
    hook_calls = []
    sent_messages = []
    loaded_sessions = []
    saved_sessions = []
    planned_actions = []

    async def fake_send_message(token, chat_id, text):
        sent_messages.append((token, chat_id, text))

    async def fake_plan_text_action(cfg, chat_id, prompt_text):
        planned_actions.append((cfg, chat_id, prompt_text))
        return RuntimeAction(type="reply", reply_text="answer")

    def fake_load_session(session_dir, chat_id):
        loaded_sessions.append((session_dir, chat_id))
        return {"messages": []}

    def fake_save_session(session_dir, chat_id, session):
        saved_sessions.append((session_dir, chat_id, session))

    def fake_hook(session_id, user_text, assistant_text):
        hook_calls.append((session_id, user_text, assistant_text))

    services = HandlerServices(
        extract_input=lambda update: TelegramInput(
            message=update["message"],
            chat_id=5785127604,
            from_id=5785127604,
            text="hello",
            prompt_text="hello",
            attachments=[],
            has_image=False,
            mode="text",
        ),
        send_message=fake_send_message,
        plan_text_action=fake_plan_text_action,
        run_post_response_hook=fake_hook,
        load_session=fake_load_session,
        save_session=fake_save_session,
        session_dir=Path("sessions"),
    )

    await handle_update(
        {"channels": {"telegram": {"botToken": "token", "allowFrom": ["5785127604"]}}},
        {"message": {"text": "hello"}},
        services=services,
    )

    assert planned_actions[0][1:] == (5785127604, "hello")
    assert sent_messages == [("token", 5785127604, "answer")]
    assert hook_calls == [("telegram-5785127604", "hello", "answer")]
    assert loaded_sessions == [(Path("sessions"), 5785127604)]
    assert saved_sessions[0][1] == 5785127604


@pytest.mark.asyncio
async def test_handle_update_text_path_can_generate_image_from_action():
    sent_messages = []
    sent_photos = []
    hook_calls = []
    saved_sessions = []
    log_messages = []

    async def fake_plan_text_action(cfg, chat_id, prompt_text):
        return RuntimeAction(
            type="reply_and_generate_image",
            reply_text="РЎРґРµР»Р°Р»Р°.",
            image_prompt="portrait in moonlight",
        )

    async def fake_complete_image_generation(cfg, chat_id, prompt_text, media_items):
        assert prompt_text == "portrait in moonlight"
        return {"answer": "generated", "image_paths": [Path("img1.png")]}

    async def fake_send_message(token, chat_id, text):
        sent_messages.append((token, chat_id, text))

    async def fake_send_photo(token, chat_id, file_path, caption=""):
        sent_photos.append((token, chat_id, file_path, caption))

    def fake_save_session(session_dir, chat_id, session):
        saved_sessions.append((session_dir, chat_id, session))

    services = HandlerServices(
        extract_input=lambda update: TelegramInput(
            message=update["message"],
            chat_id=5785127604,
            from_id=5785127604,
            text="СЃРіРµРЅРµСЂСЊ С‚Рѕ, Рѕ С‡РµРј РјС‹ РіРѕРІРѕСЂРёР»Рё",
            prompt_text="СЃРіРµРЅРµСЂСЊ С‚Рѕ, Рѕ С‡РµРј РјС‹ РіРѕРІРѕСЂРёР»Рё",
            attachments=[],
            has_image=False,
            mode="text",
        ),
        plan_text_action=fake_plan_text_action,
        complete_image_generation=fake_complete_image_generation,
        send_message=fake_send_message,
        send_photo=fake_send_photo,
        load_session=lambda session_dir, chat_id: {"messages": []},
        save_session=fake_save_session,
        log_event=lambda message: log_messages.append(message),
        run_post_response_hook=lambda session_id, user_text, assistant_text: hook_calls.append(
            (session_id, user_text, assistant_text)
        ),
        session_dir=Path("sessions"),
    )

    await handle_update(
        {"channels": {"telegram": {"botToken": "token", "allowFrom": ["5785127604"]}}},
        {"message": {"text": "СЃРіРµРЅРµСЂСЊ С‚Рѕ, Рѕ С‡РµРј РјС‹ РіРѕРІРѕСЂРёР»Рё"}},
        services=services,
    )

    assert sent_messages == [("token", 5785127604, "РЎРґРµР»Р°Р»Р°.")]
    assert sent_photos == [("token", 5785127604, Path("img1.png"), "")]
    assert hook_calls == [("telegram-5785127604", "СЃРіРµРЅРµСЂСЊ С‚Рѕ, Рѕ С‡РµРј РјС‹ РіРѕРІРѕСЂРёР»Рё", "РЎРґРµР»Р°Р»Р°.")]
    assert saved_sessions[0][2]["messages"][-1]["content"] == "РЎРґРµР»Р°Р»Р°."
    assert log_messages[0].startswith("planned action chat=5785127604 type=reply_and_generate_image")
    assert log_messages[1].startswith("image generation start chat=5785127604")
    assert log_messages[2] == "image generation result chat=5785127604 images=1 answer=True"


@pytest.mark.asyncio
async def test_handle_update_ignores_disallowed_sender():
    sent_messages = []

    async def fake_send_message(token, chat_id, text):
        sent_messages.append((token, chat_id, text))

    services = HandlerServices(
        extract_input=lambda update: TelegramInput(
            message=update["message"],
            chat_id=999,
            from_id=111,
            text="hello",
            prompt_text="hello",
            attachments=[],
            has_image=False,
            mode="text",
        ),
        send_message=fake_send_message,
    )

    await handle_update(
        {"channels": {"telegram": {"botToken": "token", "allowFrom": ["5785127604"]}}},
        {"message": {"text": "hello"}},
        services=services,
    )

    assert sent_messages == []


@pytest.mark.asyncio
async def test_handle_update_vision_path_downloads_attachments_and_sends_answer():
    downloads = []
    sent_messages = []
    hook_calls = []

    async def fake_download_attachment(token, attachment, inbound_media_dir):
        downloads.append((token, attachment["file_id"], inbound_media_dir))
        return {"data_url": "data:image/jpeg;base64,ZmFrZQ=="}

    async def fake_complete_vision(cfg, chat_id, prompt_text, media_items):
        assert prompt_text == "look"
        assert len(media_items) == 1
        return "vision-answer"

    async def fake_send_message(token, chat_id, text):
        sent_messages.append((token, chat_id, text))

    services = HandlerServices(
        extract_input=lambda update: TelegramInput(
            message=update["message"],
            chat_id=5785127604,
            from_id=5785127604,
            text="look",
            prompt_text="look",
            attachments=[{"kind": "photo", "file_id": "photo-id"}],
            has_image=True,
            mode="vision",
        ),
        download_attachment=fake_download_attachment,
        complete_vision=fake_complete_vision,
        send_message=fake_send_message,
        run_post_response_hook=lambda session_id, user_text, assistant_text: hook_calls.append(
            (session_id, user_text, assistant_text)
        ),
        inbound_media_dir=Path("inbound"),
    )

    await handle_update(
        {"channels": {"telegram": {"botToken": "token", "allowFrom": ["5785127604"]}}},
        {"message": {"caption": "look"}},
        services=services,
    )

    assert downloads == [("token", "photo-id", Path("inbound"))]
    assert sent_messages == [("token", 5785127604, "vision-answer")]
    assert hook_calls == [("telegram-5785127604", "look", "vision-answer")]


@pytest.mark.asyncio
async def test_handle_update_image_generation_path_sends_photos_then_text():
    sent_messages = []
    sent_photos = []

    async def fake_send_message(token, chat_id, text):
        sent_messages.append((token, chat_id, text))

    async def fake_send_photo(token, chat_id, file_path, caption=""):
        sent_photos.append((token, chat_id, file_path, caption))

    async def fake_complete_image_generation(cfg, chat_id, prompt_text, media_items):
        assert prompt_text == "red square"
        return {"answer": "generated", "image_paths": [Path("img1.png"), Path("img2.png")]}

    services = HandlerServices(
        extract_input=lambda update: TelegramInput(
            message=update["message"],
            chat_id=5785127604,
            from_id=5785127604,
            text="/img red square",
            prompt_text="red square",
            attachments=[],
            has_image=False,
            mode="image_generation",
        ),
        complete_image_generation=fake_complete_image_generation,
        send_message=fake_send_message,
        send_photo=fake_send_photo,
    )

    await handle_update(
        {"channels": {"telegram": {"botToken": "token", "allowFrom": ["5785127604"]}}},
        {"message": {"text": "/img red square"}},
        services=services,
    )

    assert sent_photos == [
        ("token", 5785127604, Path("img1.png"), ""),
        ("token", 5785127604, Path("img2.png"), ""),
    ]
    assert sent_messages == [("token", 5785127604, "generated")]

