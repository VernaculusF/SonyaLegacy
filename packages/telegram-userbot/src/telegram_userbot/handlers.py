from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

from telegram_userbot.media import TelegramInput, extract_telegram_input
from telegram_userbot.telegram_api import download_telegram_attachment, send_telegram_photo
from telegram_userbot.sessions import load_session, save_session
from telegram_userbot.telegram_api import send_telegram_message


def should_allow_sender(allowed: set[str], from_id: str, chat_id: str) -> bool:
    if not allowed:
        return True
    return from_id in allowed or chat_id in allowed


async def _default_complete(cfg: dict[str, Any], chat_id: int, prompt_text: str) -> str:
    raise NotImplementedError("complete service is not configured")


async def _default_complete_vision(
    cfg: dict[str, Any], chat_id: int, prompt_text: str, media_items: list[dict[str, Any]]
) -> str:
    raise NotImplementedError("complete_vision service is not configured")


async def _default_complete_image_generation(
    cfg: dict[str, Any], chat_id: int, prompt_text: str, media_items: list[dict[str, Any]]
) -> dict[str, Any]:
    raise NotImplementedError("complete_image_generation service is not configured")


async def _default_download_attachment(token: str, attachment: dict[str, Any], inbound_media_dir: Path) -> dict[str, Any]:
    return await download_telegram_attachment(token, attachment, inbound_media_dir)


def _default_hook(session_id: str, user_text: str, assistant_text: str) -> None:
    return None


@dataclass(slots=True)
class HandlerServices:
    extract_input: Callable[[dict[str, Any]], TelegramInput | None] = extract_telegram_input
    send_message: Callable[[str, int, str], Awaitable[None]] = send_telegram_message
    send_photo: Callable[[str, int, Path, str], Awaitable[Any]] = send_telegram_photo
    complete: Callable[[dict[str, Any], int, str], Awaitable[str]] = _default_complete
    complete_vision: Callable[[dict[str, Any], int, str, list[dict[str, Any]]], Awaitable[str]] = _default_complete_vision
    complete_image_generation: Callable[
        [dict[str, Any], int, str, list[dict[str, Any]]], Awaitable[dict[str, Any]]
    ] = _default_complete_image_generation
    download_attachment: Callable[[str, dict[str, Any], Path], Awaitable[dict[str, Any]]] = _default_download_attachment
    run_post_response_hook: Callable[[str, str, str], None] = _default_hook
    load_session: Callable[[Path, int], dict[str, Any]] = load_session
    save_session: Callable[[Path, int, dict[str, Any]], None] = save_session
    session_dir: Path = field(default_factory=lambda: Path("."))
    inbound_media_dir: Path = field(default_factory=lambda: Path("."))


async def handle_update(
    cfg: dict[str, Any],
    update: dict[str, Any],
    *,
    services: HandlerServices,
) -> None:
    token = (((cfg.get("channels") or {}).get("telegram") or {}).get("botToken"))
    allowed = {str(item) for item in (((cfg.get("channels") or {}).get("telegram") or {}).get("allowFrom") or [])}
    input_data = services.extract_input(update)
    if not token or not input_data or not input_data.chat_id or not input_data.from_id:
        return
    if not should_allow_sender(allowed, str(input_data.from_id), str(input_data.chat_id)):
        return

    if input_data.text == "/start":
        await services.send_message(token, input_data.chat_id, "OpenClaw bridge online.")
        return

    media_items: list[dict[str, Any]] = []
    for attachment in input_data.attachments:
        media_items.append(await services.download_attachment(token, attachment, services.inbound_media_dir))

    if input_data.mode == "image_generation":
        generated = await services.complete_image_generation(cfg, input_data.chat_id, input_data.prompt_text, media_items)
        for file_path in generated.get("image_paths", []):
            await services.send_photo(token, input_data.chat_id, Path(file_path), "")
        if generated.get("answer"):
            await services.send_message(token, input_data.chat_id, generated["answer"])
        services.run_post_response_hook(
            f"telegram-{input_data.chat_id}",
            input_data.prompt_text,
            str(generated.get("answer", "")),
        )
        return

    if input_data.mode == "vision":
        answer = await services.complete_vision(cfg, input_data.chat_id, input_data.prompt_text, media_items)
        await services.send_message(token, input_data.chat_id, answer)
        services.run_post_response_hook(f"telegram-{input_data.chat_id}", input_data.prompt_text, answer)
        return

    session = services.load_session(services.session_dir, input_data.chat_id)
    answer = await services.complete(cfg, input_data.chat_id, input_data.prompt_text)
    session["messages"] = [
        *(session.get("messages") or []),
        {"role": "user", "content": input_data.prompt_text},
        {"role": "assistant", "content": answer},
    ]
    services.save_session(services.session_dir, input_data.chat_id, session)
    await services.send_message(token, input_data.chat_id, answer)
    services.run_post_response_hook(f"telegram-{input_data.chat_id}", input_data.prompt_text, answer)
