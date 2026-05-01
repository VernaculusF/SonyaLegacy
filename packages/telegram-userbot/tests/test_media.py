import json
from pathlib import Path

from telegram_userbot.media import (
    classify_prompt,
    extract_telegram_input,
    parse_openrouter_event_stream,
)


def test_classify_prompt_detects_image_generation():
    assert classify_prompt("/img red square", False) == "image_generation"
    assert classify_prompt("hello", False) == "text"


def test_extract_telegram_input_uses_best_photo():
    payload = json.loads(
        (Path(__file__).parent / "fixtures" / "telegram_update_photo.json").read_text(
            encoding="utf-8"
        )
    )
    result = extract_telegram_input(payload)
    assert result.mode == "vision"
    assert result.attachments[0]["file_id"] == "big"


def test_parse_openrouter_event_stream_extracts_images():
    raw = (Path(__file__).parent / "fixtures" / "openrouter_image_stream.txt").read_text(
        encoding="utf-8"
    )
    parsed = parse_openrouter_event_stream(raw)
    assert len(parsed["images"]) == 1
