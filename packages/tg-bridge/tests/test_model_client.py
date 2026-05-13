from pathlib import Path

import httpx
import pytest

from tg_bridge.model_client import (
    _collapse_repeated_paragraphs,
    _looks_incomplete_text,
    _trim_overlap,
    complete_image_generation,
    complete_text,
    complete_vision,
    extract_finish_reason_from_payload,
    resolve_image_model_name,
    resolve_model_name,
    serialize_user_content,
)
from tg_bridge.prompts import build_messages


def test_resolve_model_name_strips_omniroute_prefix():
    cfg = {"agents": {"defaults": {"model": "omniroute/openrouter/google/gemma-4-26b-a4b-it:free"}}}
    assert resolve_model_name(cfg) == "openrouter/google/gemma-4-26b-a4b-it:free"


def test_resolve_image_model_name_uses_configured_image_model():
    cfg = {
        "agents": {
            "defaults": {
                "model": "omniroute/openrouter/google/gemma-4-26b-a4b-it:free",
                "imageModel": "omniroute/openrouter/google/gemini-2.5-flash-image-preview:free",
            }
        }
    }
    assert resolve_image_model_name(cfg) == "openrouter/google/gemini-2.5-flash-image-preview:free"


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


def test_serialize_user_content_supports_video_parts():
    payload = serialize_user_content("look", [{"data_url": "data:video/mp4;base64,ZmFrZQ==", "mime_type": "video/mp4"}])
    assert isinstance(payload, list)
    assert payload[1]["type"] == "video_url"
    assert payload[1]["videoUrl"]["url"].startswith("data:video/mp4;base64,")


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


def test_extract_finish_reason_from_payload_reads_choice_value():
    payload = {"choices": [{"finish_reason": "length", "message": {"content": "partial"}}]}
    assert extract_finish_reason_from_payload(payload) == "length"


def test_looks_incomplete_text_detects_obvious_cutoff():
    assert not _looks_incomplete_text("Это")
    assert not _looks_incomplete_text("Я чувствую, как")
    assert _looks_incomplete_text(("Почти закончено... " * 20).strip())
    assert not _looks_incomplete_text("Все хорошо.")
    assert not _looks_incomplete_text("Я рядом 🖤")


def test_trim_overlap_discards_repeated_prefix_from_continuation():
    existing = "Первая часть ответа. Вторая часть ответа."
    new_part = "Вторая часть ответа. Третья часть ответа."
    assert _trim_overlap(existing, new_part) == "Третья часть ответа."


def test_collapse_repeated_paragraphs_removes_looped_blocks():
    text = "Абзац один.\n\nАбзац два.\n\nАбзац один.\n\nАбзац два.\n\nАбзац три."
    assert _collapse_repeated_paragraphs(text) == "Абзац один.\n\nАбзац два.\n\nАбзац три."


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
async def test_complete_text_continues_when_finish_reason_is_length():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(
                200,
                json={"choices": [{"finish_reason": "length", "message": {"content": "first part"}}]},
            )
        return httpx.Response(
            200,
            json={"choices": [{"finish_reason": "stop", "message": {"content": " second part"}}]},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        answer = await complete_text(
            {"baseUrl": "http://localhost:20128/v1", "apiKey": "x"},
            "model",
            [{"role": "user", "content": "hello"}],
            client=client,
        )
    assert calls["count"] == 2
    assert answer == "first part second part"


@pytest.mark.asyncio
async def test_complete_text_preserves_newlines_across_continuation():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(
                200,
                json={"choices": [{"finish_reason": "length", "message": {"content": "Абзац один.\n\n"}}]},
            )
        return httpx.Response(
            200,
            json={"choices": [{"finish_reason": "stop", "message": {"content": "Абзац два."}}]},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        answer = await complete_text(
            {"baseUrl": "http://localhost:20128/v1", "apiKey": "x"},
            "model",
            [{"role": "user", "content": "hello"}],
            client=client,
        )
    assert calls["count"] == 2
    assert answer == "Абзац один.\n\nАбзац два."


@pytest.mark.asyncio
async def test_complete_text_continues_when_reply_looks_cut_off_even_without_length():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(
                200,
                json={"choices": [{"finish_reason": "stop", "message": {"content": "А" * 260}}]},
            )
        return httpx.Response(
            200,
            json={"choices": [{"finish_reason": "stop", "message": {"content": "завершение."}}]},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        answer = await complete_text(
            {"baseUrl": "http://localhost:20128/v1", "apiKey": "x"},
            "model",
            [{"role": "user", "content": "hello"}],
            client=client,
        )
    assert calls["count"] == 2
    assert answer == f"{'А' * 260} завершение."


@pytest.mark.asyncio
async def test_complete_text_deduplicates_repeated_continuation_block():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(
                200,
                json={"choices": [{"finish_reason": "length", "message": {"content": "Первая часть. Вторая часть."}}]},
            )
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"finish_reason": "stop", "message": {"content": "Вторая часть. Третья часть закончена."}}
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        answer = await complete_text(
            {"baseUrl": "http://localhost:20128/v1", "apiKey": "x"},
            "model",
            [{"role": "user", "content": "hello"}],
            client=client,
        )
    assert calls["count"] == 2
    assert answer == "Первая часть. Вторая часть. Третья часть закончена."


@pytest.mark.asyncio
async def test_complete_text_retries_when_provider_returns_empty_message():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(
                200,
                json={"choices": [{"finish_reason": "stop", "message": {"content": ""}}]},
            )
        return httpx.Response(
            200,
            json={"choices": [{"finish_reason": "stop", "message": {"content": "answer after retry"}}]},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        answer = await complete_text(
            {"baseUrl": "http://localhost:20128/v1", "apiKey": "x"},
            "model",
            [{"role": "user", "content": "hello"}],
            client=client,
        )
    assert calls["count"] == 2
    assert answer == "answer after retry"


@pytest.mark.asyncio
async def test_complete_text_retries_on_transient_provider_502():
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(502, text="bad gateway")
        return httpx.Response(
            200,
            json={"choices": [{"finish_reason": "stop", "message": {"content": "answer after 502 retry"}}]},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        answer = await complete_text(
            {"baseUrl": "http://localhost:20128/v1", "apiKey": "x"},
            "model",
            [{"role": "user", "content": "hello"}],
            client=client,
        )
    assert calls["count"] == 2
    assert answer == "answer after 502 retry"


@pytest.mark.asyncio
async def test_complete_image_generation_saves_images_from_json_payload(tmp_path: Path):
    def handler(request: httpx.Request) -> httpx.Response:
        body = request.read().decode("utf-8")
        compact = body.replace(" ", "").lower()
        assert '"model":"image-model"' in compact
        assert '"stream":false' in compact
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "Done. Image ready",
                            "images": [{"image_url": {"url": "data:image/png;base64,ZmFrZQ=="}}],
                        }
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        result = await complete_image_generation(
            {"baseUrl": "http://localhost:20128/v1", "apiKey": "x"},
            "image-model",
            [{"role": "user", "content": "draw cat"}],
            output_dir=tmp_path,
            chat_id=123,
            client=client,
        )
    assert result["answer"] == "Done. Image ready"
    assert len(result["image_paths"]) == 1
    assert result["image_paths"][0].exists()


@pytest.mark.asyncio
async def test_complete_image_generation_supports_stream_payloads(tmp_path: Path):
    stream = (
        'data: {"choices":[{"delta":{"content":"Done. ","images":[{"image_url":{"url":"data:image/png;base64,ZmFrZQ=="}}]}}]}\n'
        'data: {"choices":[{"delta":{"content":"Image ready"},"finish_reason":"stop"}]}\n'
        "data: [DONE]\n"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        body = request.read().decode("utf-8")
        compact = body.replace(" ", "").lower()
        assert '"stream":true' in compact
        return httpx.Response(200, text=stream)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        result = await complete_image_generation(
            {"baseUrl": "http://localhost:20128/v1", "apiKey": "x"},
            "image-model",
            [{"role": "user", "content": "draw cat"}],
            output_dir=tmp_path,
            chat_id=123,
            client=client,
            stream=True,
        )
    assert result["answer"] == "Done. Image ready"
    assert len(result["image_paths"]) == 1

