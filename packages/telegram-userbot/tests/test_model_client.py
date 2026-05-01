from pathlib import Path

import httpx
import pytest

from telegram_userbot.model_client import (
    complete_image_generation,
    complete_text,
    complete_vision,
    resolve_model_name,
    serialize_user_content,
)
from telegram_userbot.prompts import build_messages


def test_resolve_model_name_strips_omniroute_prefix():
    cfg = {"agents": {"defaults": {"model": "omniroute/openrouter/google/gemma-4-26b-a4b-it:free"}}}
    assert resolve_model_name(cfg) == "openrouter/google/gemma-4-26b-a4b-it:free"


def test_build_messages_includes_bootstrap_and_user_message():
    bootstrap = {"agents": "a", "soul": "b", "heartbeat": "c", "identity": "", "memoryContext": "d"}
    session = {"messages": []}
    messages = build_messages(bootstrap, session, "hello", "English")
    assert messages[0]["role"] == "system"
    assert messages[-1]["content"] == "hello"


def test_serialize_user_content_returns_multipart_when_media_present():
    payload = serialize_user_content("look", [{"data_url": "data:image/png;base64,ZmFrZQ=="}])
    assert isinstance(payload, list)
    assert payload[0]["type"] == "text"
    assert payload[1]["type"] == "image_url"


@pytest.mark.asyncio
async def test_complete_text_parses_openai_payload():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("http://localhost:20128/v1/chat/completions")
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "answer"}}]},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        answer = await complete_text(
            {"baseUrl": "http://localhost:20128/v1", "apiKey": "x"},
            "model",
            [{"role": "user", "content": "hello"}],
            client=client,
        )
    assert answer == "answer"


@pytest.mark.asyncio
async def test_complete_vision_uses_same_payload_shape():
    def handler(request: httpx.Request) -> httpx.Response:
        body = request.read().decode("utf-8")
        assert '"model":"model"' in body.replace(" ", "")
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "vision-answer"}}]},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        answer = await complete_vision(
            {"baseUrl": "http://localhost:20128/v1", "apiKey": "x"},
            "model",
            [{"role": "user", "content": [{"type": "text", "text": "look"}]}],
            client=client,
        )
    assert answer == "vision-answer"


@pytest.mark.asyncio
async def test_complete_image_generation_saves_images(tmp_path: Path):
    stream = (
        'data: {"choices":[{"delta":{"content":"Done. ","images":[{"image_url":{"url":"data:image/png;base64,ZmFrZQ=="}}]}}]}\n'
        'data: {"choices":[{"delta":{"content":"Image ready"},"finish_reason":"stop"}]}\n'
        "data: [DONE]\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=stream)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        result = await complete_image_generation(
            {"baseUrl": "http://localhost:20128/v1", "apiKey": "x"},
            [{"role": "user", "content": "draw cat"}],
            output_dir=tmp_path,
            chat_id=123,
            client=client,
        )
    assert result["answer"] == "Done. Image ready"
    assert len(result["image_paths"]) == 1
    assert result["image_paths"][0].exists()
