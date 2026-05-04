import json
from pathlib import Path

from tg_bridge.media import (
    classify_prompt,
    extract_telegram_input,
    parse_openrouter_event_stream,
)


def test_classify_prompt_detects_image_generation():
    assert classify_prompt("/img red square", False) == "image_generation"
    assert classify_prompt("нарисуй красный квадрат", False) == "image_generation"
    assert classify_prompt("hello", False) == "text"


def test_extract_telegram_input_uses_best_photo():
    payload = json.loads(
        (Path(__file__).parent / "fixtures" / "telegram_update_photo.json").read_text(
            encoding="utf-8-sig"
        )
    )
    result = extract_telegram_input(payload)
    assert result.mode == "vision"
    assert result.attachments[0]["file_id"] == "big"
    assert result.prompt_text == "look"


def test_extract_telegram_input_uses_image_fallback_prompt_without_caption():
    payload = {
        "message": {
            "chat": {"id": 1},
            "from": {"id": 2},
            "photo": [
                {"file_id": "small", "file_size": 1, "width": 10, "height": 10},
                {"file_id": "big", "file_size": 2, "width": 20, "height": 20},
            ],
        }
    }
    result = extract_telegram_input(payload)
    assert result is not None
    assert result.mode == "vision"
    assert result.attachments[0]["file_id"] == "big"
    assert result.prompt_text == "Пользователь прислал изображение. Определи, что на нём, и ответь естественно по контексту."


def test_extract_telegram_input_uses_sticker_fallback_prompt():
    payload = {
        "message": {
            "chat": {"id": 1},
            "from": {"id": 2},
            "sticker": {
                "file_id": "sticker-id",
                "file_unique_id": "unique",
                "emoji": "рџ–¤",
                "is_animated": False,
                "is_video": False,
            },
        }
    }
    result = extract_telegram_input(payload)
    assert result is not None
    assert result.mode == "vision"
    assert result.prompt_text == "Пользователь прислал стикер. Определи, что на нём изображено, и ответь естественно по контексту."


def test_extract_telegram_input_uses_video_fallback_prompt():
    payload = {
        "message": {
            "chat": {"id": 1},
            "from": {"id": 2},
            "video": {
                "file_id": "video-id",
                "file_unique_id": "video-unique",
                "mime_type": "video/mp4",
                "duration": 5,
                "width": 320,
                "height": 240,
            },
        }
    }
    result = extract_telegram_input(payload)
    assert result is not None
    assert result.mode == "vision"
    assert result.attachments[0]["kind"] == "video"
    assert result.prompt_text == "Пользователь прислал видео. Определи, что происходит в ролике, и ответь естественно по контексту."


def test_parse_openrouter_event_stream_extracts_images():
    raw = (Path(__file__).parent / "fixtures" / "openrouter_image_stream.txt").read_text(
        encoding="utf-8"
    )
    parsed = parse_openrouter_event_stream(raw)
    assert len(parsed["images"]) == 1

