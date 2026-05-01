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

from telegram_userbot.adapters.openclaw import OpenClawHost
from telegram_userbot.bootstrap import load_bootstrap_context
from telegram_userbot.handlers import HandlerServices, handle_update
from telegram_userbot.hooks import run_python_hook
from telegram_userbot.logging import append_log_line, format_error
from telegram_userbot.model_client import (
    complete_image_generation,
    complete_text,
    complete_vision,
    resolve_model_name,
    serialize_user_content,
)
from telegram_userbot.prompts import build_messages
from telegram_userbot.sessions import load_session
from telegram_userbot.state import read_state, write_state
from telegram_userbot.telegram_api import get_updates
from telegram_userbot.update_loop import poll_once


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
) -> dict[str, Any]:
    try:
        result = subprocess.run(
            [str(python_executable), str(script_path), *args],
            cwd=str(workspace_root),
            env={**os.environ, "OPENCLAW_WORKSPACE": str(workspace_root)},
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


def _compose_services(host: OpenClawHost, cfg: dict[str, Any], python_executable: Path) -> HandlerServices:
    provider = _provider_from_cfg(cfg)
    model_name = resolve_model_name(cfg)

    def runner(script_path: Path, args: list[str]) -> dict[str, Any]:
        return _run_python_script(python_executable, host.workspace_root, script_path, args)

    async def complete_text_service(cfg_: dict[str, Any], chat_id: int, prompt_text: str) -> str:
        bootstrap = load_bootstrap_context(host, runner)
        session = load_session(host.session_dir, chat_id)
        messages = build_messages(bootstrap, session, prompt_text)
        answer = await complete_text(provider, model_name, messages)
        return answer or "Пустой ответ модели."

    async def complete_vision_service(
        cfg_: dict[str, Any], chat_id: int, prompt_text: str, media_items: list[dict[str, Any]]
    ) -> str:
        bootstrap = load_bootstrap_context(host, runner)
        session = load_session(host.session_dir, chat_id)
        messages = build_messages(bootstrap, session, serialize_user_content(prompt_text, media_items))
        answer = await complete_vision(provider, model_name, messages)
        return answer or "Пустой ответ модели на изображение."

    async def complete_image_generation_service(
        cfg_: dict[str, Any], chat_id: int, prompt_text: str, media_items: list[dict[str, Any]]
    ) -> dict[str, Any]:
        bootstrap = load_bootstrap_context(host, runner)
        session = load_session(host.session_dir, chat_id)
        messages = build_messages(bootstrap, session, serialize_user_content(prompt_text, media_items))
        generated = await complete_image_generation(
            provider,
            messages,
            output_dir=host.generated_media_dir,
            chat_id=chat_id,
        )
        return generated

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

    return HandlerServices(
        complete=complete_text_service,
        complete_vision=complete_vision_service,
        complete_image_generation=complete_image_generation_service,
        run_post_response_hook=run_hook,
        session_dir=host.session_dir,
        inbound_media_dir=host.inbound_media_dir,
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
