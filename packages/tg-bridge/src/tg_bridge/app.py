from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any

from sonya_runtime.tasks.service import TaskService
from sonya_runtime.tasks.sqlite_store import SQLiteTaskStore
from tg_bridge.actions import RuntimeAction, parse_runtime_action
from tg_bridge.adapters.openclaw import OpenClawHost
from tg_bridge.bootstrap import load_bootstrap_context
from tg_bridge.handlers import HandlerServices, handle_update
from tg_bridge.hooks import run_python_hook
from tg_bridge.logging import append_log_line, format_error
from tg_bridge.model_client import (
    complete_image_generation,
    complete_text,
    complete_vision,
    resolve_image_model_name,
    resolve_model_name,
    serialize_user_content,
)
from tg_bridge.prompts import build_action_messages, build_messages
from tg_bridge.sessions import load_session
from tg_bridge.state import read_state, write_state
from tg_bridge.telegram_api import get_updates
from tg_bridge.telegram_api import send_telegram_message, send_telegram_photo
from tg_bridge.update_loop import poll_once


@dataclass(slots=True)
class BridgeApp:
    host: OpenClawHost


def create_openclaw_app(root: Path | str) -> BridgeApp:
    return BridgeApp(host=OpenClawHost(Path(root)))


def _run_python_script(
    python_executable: Path,
    workspace_root: Path,
    script_path: Path,
    args: list[str],
    extra_env: dict[str, str] | None = None,
) -> dict[str, Any]:
    try:
        result = subprocess.run(
            [str(python_executable), str(script_path), *args],
            cwd=str(workspace_root),
            env={**os.environ, "OPENCLAW_WORKSPACE": str(workspace_root), **(extra_env or {})},
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "status": result.returncode,
            "error": None,
        }
    except Exception as err:
        return {"stdout": "", "stderr": "", "status": -1, "error": err}


def _provider_from_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    provider = (((cfg.get("models") or {}).get("providers") or {}).get("omniroute"))
    if not provider or not provider.get("baseUrl") or not provider.get("apiKey"):
        raise RuntimeError("omniroute model provider is not configured")
    return provider


async def _plan_text_action_with_fallback(
    provider: dict[str, Any],
    model_name: str,
    bootstrap: dict[str, str],
    session: dict[str, Any],
    prompt_text: str,
) -> RuntimeAction:
    async def _complete_normal_reply() -> str:
        fallback_messages = build_messages(bootstrap, session, prompt_text)
        return await complete_text(provider, model_name, fallback_messages)

    action_messages = build_action_messages(bootstrap, session, prompt_text)
    raw = await complete_text(provider, model_name, action_messages)
    action = parse_runtime_action(raw)
    if action is not None:
        if action.type == "generate_image" and action.image_prompt:
            return action
        if action.type in {"create_task", "reply_and_create_task", "ask_clarification", "report_limitation"}:
            return action
        if action.type == "reply":
            fallback_reply = await _complete_normal_reply()
            if fallback_reply:
                return RuntimeAction(type="reply", reply_text=fallback_reply)
            if action.reply_text:
                return action
        if action.type == "reply_and_generate_image" and action.image_prompt:
            fallback_reply = await _complete_normal_reply()
            if fallback_reply:
                return RuntimeAction(
                    type="reply_and_generate_image",
                    reply_text=fallback_reply,
                    image_prompt=action.image_prompt,
                )
            if action.reply_text:
                return action

    fallback_reply = await _complete_normal_reply()
    if fallback_reply:
        return RuntimeAction(type="reply", reply_text=fallback_reply)
    return RuntimeAction(type="reply", reply_text=raw or "Пустой ответ модели.")


def _compose_services(host: OpenClawHost, cfg: dict[str, Any], python_executable: Path) -> HandlerServices:
    provider = _provider_from_cfg(cfg)
    model_name = resolve_model_name(cfg)
    image_model_name = resolve_image_model_name(cfg)
    task_service = TaskService(SQLiteTaskStore(host.tasks_db_path))

    def runner(script_path: Path, args: list[str], extra_env: dict[str, str] | None = None) -> dict[str, Any]:
        return _run_python_script(python_executable, host.workspace_root, script_path, args, extra_env)

    async def complete_text_service(cfg_: dict[str, Any], chat_id: int, prompt_text: str) -> str:
        session_id = f"telegram-{chat_id}"
        bootstrap = load_bootstrap_context(host, runner, session_id=session_id)
        session = load_session(host.session_dir, chat_id)
        messages = build_messages(bootstrap, session, prompt_text)
        answer = await complete_text(provider, model_name, messages)
        return answer or "Пустой ответ модели."

    async def plan_text_action_service(cfg_: dict[str, Any], chat_id: int, prompt_text: str) -> RuntimeAction:
        session_id = f"telegram-{chat_id}"
        bootstrap = load_bootstrap_context(host, runner, session_id=session_id)
        session = load_session(host.session_dir, chat_id)
        return await _plan_text_action_with_fallback(provider, model_name, bootstrap, session, prompt_text)

    async def complete_vision_service(
        cfg_: dict[str, Any], chat_id: int, prompt_text: str, media_items: list[dict[str, Any]]
    ) -> str:
        session_id = f"telegram-{chat_id}"
        bootstrap = load_bootstrap_context(host, runner, session_id=session_id)
        session = load_session(host.session_dir, chat_id)
        messages = build_messages(bootstrap, session, serialize_user_content(prompt_text, media_items))
        answer = await complete_vision(provider, model_name, messages)
        return answer or "Пустой ответ модели на изображение."

    async def complete_image_generation_service(
        cfg_: dict[str, Any], chat_id: int, prompt_text: str, media_items: list[dict[str, Any]]
    ) -> dict[str, Any]:
        session_id = f"telegram-{chat_id}"
        bootstrap = load_bootstrap_context(host, runner, session_id=session_id)
        session = load_session(host.session_dir, chat_id)
        messages = build_messages(bootstrap, session, serialize_user_content(prompt_text, media_items))
        return await complete_image_generation(
            provider,
            image_model_name,
            messages,
            output_dir=host.generated_media_dir,
            chat_id=chat_id,
        )

    def run_hook(session_id: str, user_text: str, assistant_text: str) -> None:
        result = run_python_hook(
            python_executable,
            host.post_response_hook_path,
            host.workspace_root,
            session_id,
            user_text,
            assistant_text,
        )
        if result.returncode != 0:
            append_log_line(host.bridge_log_path, f"post_response_hook exit={result.returncode} stderr={result.stderr.strip()}")

    def log_event(message: str) -> None:
        append_log_line(host.bridge_log_path, message)

    async def send_message_service(token: str, chat_id: int, text: str) -> None:
        await send_telegram_message(token, chat_id, text, log_error=log_event)

    async def send_photo_service(token: str, chat_id: int, file_path: Path, caption: str = "") -> Any:
        result = await send_telegram_photo(token, chat_id, file_path, caption)
        log_event(f"sendPhoto success chat={chat_id} file={Path(file_path).name} message_id={result.get('message_id')}")
        return result

    return HandlerServices(
        send_message=send_message_service,
        send_photo=send_photo_service,
        complete=complete_text_service,
        complete_vision=complete_vision_service,
        complete_image_generation=complete_image_generation_service,
        plan_text_action=plan_text_action_service,
        run_post_response_hook=run_hook,
        log_event=log_event,
        session_dir=host.session_dir,
        inbound_media_dir=host.inbound_media_dir,
        task_service=task_service,
    )


async def run_bridge(host: OpenClawHost, *, once: bool = False, python_executable: Path | None = None) -> None:
    python_executable = python_executable or Path(sys.executable)
    append_log_line(host.bridge_log_path, "bridge starting")
    state = read_state(host.state_path)

    while True:
        try:
            cfg = host.load_config()
            token = (((cfg.get("channels") or {}).get("telegram") or {}).get("botToken"))
            if not token:
                raise RuntimeError("telegram bot token is not configured")
            services = _compose_services(host, cfg, python_executable)
            await poll_once(
                token=token,
                cfg=cfg,
                state=state,
                get_updates=get_updates,
                handle_update=partial(handle_update, services=services),
                write_state=lambda new_state: write_state(host.state_path, new_state),
                raw_updates_path=host.raw_updates_path,
            )
            if once:
                return
        except Exception as err:
            append_log_line(host.bridge_log_path, f"poll failed: {format_error(err)}")
            if once:
                raise
            await asyncio.sleep(5)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--openclaw-root", default=r"C:\Users\Jester\.openclaw")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args(argv)
    app = create_openclaw_app(Path(args.openclaw_root))
    asyncio.run(run_bridge(app.host, once=args.once))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
