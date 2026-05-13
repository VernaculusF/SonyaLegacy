from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Awaitable, Callable

from sonya_runtime.actions.models import RuntimeAction
from sonya_runtime.actions.policy import looks_like_task_status_query
from sonya_runtime.tasks.service import TaskService
from tg_bridge.media import TelegramInput, extract_telegram_input
from tg_bridge.sessions import load_session, save_session
from tg_bridge.telegram_api import (
    download_telegram_attachment,
    send_telegram_message,
    send_telegram_photo,
)


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


async def _default_plan_text_action(cfg: dict[str, Any], chat_id: int, prompt_text: str) -> RuntimeAction:
    raise NotImplementedError("plan_text_action service is not configured")


async def _default_download_attachment(token: str, attachment: dict[str, Any], inbound_media_dir: Path) -> dict[str, Any]:
    return await download_telegram_attachment(token, attachment, inbound_media_dir)


def _default_hook(session_id: str, user_text: str, assistant_text: str) -> None:
    return None


def _default_log_event(message: str) -> None:
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
    plan_text_action: Callable[[dict[str, Any], int, str], Awaitable[RuntimeAction]] = _default_plan_text_action
    download_attachment: Callable[[str, dict[str, Any], Path], Awaitable[dict[str, Any]]] = _default_download_attachment
    run_post_response_hook: Callable[[str, str, str], None] = _default_hook
    log_event: Callable[[str], None] = _default_log_event
    load_session: Callable[[Path, int], dict[str, Any]] = load_session
    save_session: Callable[[Path, int, dict[str, Any]], None] = save_session
    session_dir: Path = field(default_factory=lambda: Path("."))
    inbound_media_dir: Path = field(default_factory=lambda: Path("."))
    task_service: TaskService | None = None


def _assistant_text_for_generated(action: RuntimeAction, generated: dict[str, Any]) -> str:
    if action.reply_text:
        return action.reply_text
    if generated.get("answer"):
        return str(generated["answer"])
    if action.image_prompt:
        return f"[generated image] {action.image_prompt}"
    return "[generated image]"


def _append_session_messages(
    session: dict[str, Any],
    user_text: str,
    assistant_text: str,
    task_ref: str = "",
) -> dict[str, Any]:
    assistant_content = assistant_text
    if task_ref:
        assistant_content = f"{assistant_content}\n\n[task_ref:{task_ref}]"
    session["messages"] = [
        *(session.get("messages") or []),
        {"role": "user", "content": user_text},
        {"role": "assistant", "content": assistant_content},
    ]
    return session


async def _execute_generated_action(
    token: str,
    chat_id: int,
    user_text: str,
    action: RuntimeAction,
    cfg: dict[str, Any],
    media_items: list[dict[str, Any]],
    services: HandlerServices,
) -> str:
    prompt_text = action.image_prompt or user_text
    services.log_event(
        f"image generation start chat={chat_id} prompt={prompt_text[:200]!r} reply_text={bool(action.reply_text)}"
    )
    generated = await services.complete_image_generation(cfg, chat_id, prompt_text, media_items)
    services.log_event(
        f"image generation result chat={chat_id} images={len(generated.get('image_paths', []))} answer={bool(generated.get('answer'))}"
    )
    if action.reply_text:
        await services.send_message(token, chat_id, action.reply_text)
    for file_path in generated.get("image_paths", []):
        await services.send_photo(token, chat_id, Path(file_path), "")
    if generated.get("answer") and not action.reply_text:
        await services.send_message(token, chat_id, generated["answer"])
    return _assistant_text_for_generated(action, generated)


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
        assistant_text = await _execute_generated_action(
            token,
            input_data.chat_id,
            input_data.prompt_text,
            RuntimeAction(type="generate_image", image_prompt=input_data.prompt_text),
            cfg,
            media_items,
            services,
        )
        services.run_post_response_hook(f"telegram-{input_data.chat_id}", input_data.prompt_text, assistant_text)
        return

    if input_data.mode == "vision":
        answer = await services.complete_vision(cfg, input_data.chat_id, input_data.prompt_text, media_items)
        await services.send_message(token, input_data.chat_id, answer)
        services.run_post_response_hook(f"telegram-{input_data.chat_id}", input_data.prompt_text, answer)
        return

    session = services.load_session(services.session_dir, input_data.chat_id)
    principal_id = str(input_data.from_id)
    origin_chat_id = str(input_data.chat_id)
    task_ref = ""

    if services.task_service and looks_like_task_status_query(input_data.prompt_text):
        response = services.task_service.build_task_status_response(principal_id, origin_chat_id)
        await services.send_message(token, input_data.chat_id, response.text)
        services.save_session(
            services.session_dir,
            input_data.chat_id,
            _append_session_messages(session, input_data.prompt_text, response.text, response.task_ref or ""),
        )
        services.run_post_response_hook(f"telegram-{input_data.chat_id}", input_data.prompt_text, response.text)
        return

    action = await services.plan_text_action(cfg, input_data.chat_id, input_data.prompt_text)
    services.log_event(
        f"planned action chat={input_data.chat_id} type={action.type} has_reply={bool(action.reply_text)} has_image_prompt={bool(action.image_prompt)} has_task_payload={bool(action.task_payload)}"
    )

    if action.type == "reply":
        assistant_text = action.reply_text
        await services.send_message(token, input_data.chat_id, assistant_text)
    elif action.type in {"generate_image", "reply_and_generate_image"}:
        assistant_text = await _execute_generated_action(
            token,
            input_data.chat_id,
            input_data.prompt_text,
            action,
            cfg,
            media_items,
            services,
        )
    elif action.type in {"create_task", "reply_and_create_task"}:
        if services.task_service is None:
            raise RuntimeError("task_service is not configured")
        task = services.task_service.create_task_from_action(action)
        response = services.task_service.build_task_created_response(task, action.reply_text)
        assistant_text = response.text
        task_ref = task.task_id
        await services.send_message(token, input_data.chat_id, assistant_text)
    elif action.type in {"ask_clarification", "report_limitation"}:
        assistant_text = action.reply_text
        await services.send_message(token, input_data.chat_id, assistant_text)
    else:
        raise RuntimeError(f"unsupported runtime action: {action.type}")

    services.save_session(
        services.session_dir,
        input_data.chat_id,
        _append_session_messages(session, input_data.prompt_text, assistant_text, task_ref),
    )
    services.run_post_response_hook(f"telegram-{input_data.chat_id}", input_data.prompt_text, assistant_text)
