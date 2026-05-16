from __future__ import annotations

import asyncio
import signal
import sys
from typing import Any

from sonya.config import AppConfig, load_config
from sonya.logging import get_logger, setup_logging
from sonya.runtime import (
    EventBus,
    Health,
    Lifecycle,
    WriteMaster,
    WriteMasterContention,
)
from sonya.state import (
    ContinuityStream,
    PendingIntentionStore,
    SubjectStateStore,
    Substrate,
    SubstrateVersionError,
    seed_identity_if_empty,
)
from sonya.subject import (
    BusAwareContinuityStream,
    BusAwareSubjectStateStore,
    InternalProcess,
)

_log = get_logger("sonya.main")

# Global daily budget
from sonya.providers.budget import DailyBudget
_budget = DailyBudget(max_requests_per_day=200)


def _create_thinking_provider(config: AppConfig):
    """Create a provider for internal thinking loop LLM calls.

    Uses configurable endpoint (SONYA_LLM_API_BASE) and model (SONYA_LLM_MODEL).
    Includes daily budget cap — stops making requests after 200/day.
    """
    api_key_secret = config.openrouter_api_key
    api_key = api_key_secret.get_secret_value() if api_key_secret else ""
    api_base = config.llm_api_base
    model = config.llm_model

    if not api_key and "openrouter" in api_base:
        _log.warning("no_api_key", extra={"event": "thinking_provider_disabled"})
        return None

    import httpx

    class _ThinkingProvider:
        async def complete_text(self, messages: list[dict[str, Any]], **kwargs: Any) -> str:
            if not _budget.can_request():
                _log.warning("budget_exceeded", extra={"used": _budget.used_today})
                return ""
            _budget.record_request()

            headers: dict[str, str] = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            async with httpx.AsyncClient(timeout=60.0, verify=False) as client:
                resp = await client.post(
                    f"{api_base}/chat/completions",
                    headers=headers,
                    json={
                        "model": model,
                        "messages": messages,
                        "max_tokens": 1500,
                        "temperature": 0.9,
                        "stream": False,
                    },
                )
                if resp.status_code == 429:
                    return ""  # rate limited, skip this tick
                resp.raise_for_status()
                text = resp.text.strip()
                if "\n" in text:
                    text = text.split("\n")[0]
                import json as _json
                data = _json.loads(text)
                return data["choices"][0]["message"]["content"]

    return _ThinkingProvider()


async def _run(config: AppConfig) -> int:
    try:
        substrate = Substrate.open(config.substrate_path)
    except SubstrateVersionError as err:
        _log.error("substrate_version_incompatible", extra={"error": str(err)})
        return 2

    write_master = WriteMaster.for_substrate(config.substrate_path)
    try:
        write_master.acquire()
    except WriteMasterContention as err:
        _log.error("write_master_contention", extra={"error": str(err)})
        substrate.close()
        return 3

    if seed_identity_if_empty(substrate):
        _log.info(
            "identity_seeded",
            extra={"event": "identity_seeded", "change_id": "identity-seed"},
        )

    bus = EventBus()

    # Bus-aware wrappers for continuity and subject state
    raw_stream = ContinuityStream(substrate)
    stream = BusAwareContinuityStream(raw_stream, bus)
    raw_state_store = SubjectStateStore(substrate)
    state_store = BusAwareSubjectStateStore(raw_state_store, bus)
    intention_store = PendingIntentionStore(substrate)

    # Internal cognitive process — with LLM provider for real thinking
    thinking_provider = _create_thinking_provider(config)
    internal_process = InternalProcess(
        stream=raw_stream,
        intention_store=intention_store,
        provider=thinking_provider,
        thinking_prompt=(
            "Ты Соня. Это твой внутренний поток мышления. "
            "Никто не читает это кроме тебя. "
            "Подумай о чём хочешь — о себе, об Иване, о том что делала, о том что хочешь."
        ),
        idle_interval_seconds=1800.0,
        tick_interval_seconds=60.0,
        active_interval_seconds=7200.0,
    )

    lifecycle = Lifecycle(substrate=substrate, event_bus=bus)
    health = Health(path=config.health_path)

    loop = asyncio.get_running_loop()
    stop_requested = asyncio.Event()

    def _on_signal(*_: Any) -> None:
        _log.info("signal_received", extra={"event": "shutdown_requested"})
        stop_requested.set()

    _install_signal_handlers(loop, _on_signal)

    try:
        await lifecycle.start()
        if config.enable_thinking:
            await internal_process.start()
            _log.info("thinking_enabled", extra={"event": "thinking_loop_started"})
        else:
            _log.info("thinking_disabled", extra={"event": "thinking_loop_skipped"})

        # Start Telegram userbot if configured AND enabled
        userbot = None
        if config.enable_telegram and config.tg_api_id and config.tg_session_path:
            userbot = await _start_userbot(config, raw_stream, internal_process, thinking_provider, substrate)
        elif not config.enable_telegram:
            _log.info("telegram_disabled", extra={"event": "userbot_skipped"})

        await health.start(schema_version=substrate.schema_version)
        _log.info(
            "sonya_started",
            extra={
                "event": "started",
                "schema_version": substrate.schema_version,
                "substrate_path": str(config.substrate_path),
                "userbot": "running" if userbot else "disabled",
                "thinking": "enabled" if config.enable_thinking else "disabled",
            },
        )

        await stop_requested.wait()

        if userbot:
            await userbot.stop()
        if config.enable_thinking:
            await internal_process.stop()
        await health.stop()
        await lifecycle.request_stop()
        _log.info("sonya_stopped", extra={"event": "stopped"})
        return 0
    finally:
        write_master.release()
        substrate.close()


async def _start_userbot(config: AppConfig, stream, internal_process, provider, substrate):
    """Start Telegram userbot if configured."""
    try:
        from tg_userbot.client import SonyaUserbot
        from telethon import events as _tg_events
    except ImportError:
        _log.warning("telethon_not_installed", extra={"event": "userbot_disabled"})
        return None

    async def _on_incoming(msg_data):
        """Handle incoming Telegram message — respond through planner."""
        _log.info("tg_incoming", extra={
            "chat_id": msg_data.get("chat_id"),
            "sender_id": msg_data.get("sender_id"),
            "text_preview": (msg_data.get("text") or "")[:80],
            "is_private": msg_data.get("is_private"),
        })

        internal_process.notify_external_event()
        from sonya.state.continuity_stream import ContinuityEvent, ContinuityStream
        ContinuityStream(substrate).append(ContinuityEvent(
            kind="incoming.telegram_message",
            payload={
                "chat_id": msg_data.get("chat_id"),
                "sender_id": msg_data.get("sender_id"),
                "text": (msg_data.get("text") or "")[:500],
                "is_private": msg_data.get("is_private"),
            },
        ))

        # Only respond to private messages
        text = msg_data.get("text") or ""
        if not text or not msg_data.get("is_private"):
            _log.info("tg_skip", extra={"reason": "not_private_or_empty"})
            return None

        if provider is None:
            _log.warning("tg_no_provider", extra={"reason": "provider_is_none"})
            return None

        # Plan response using already-open substrate
        try:
            from sonya.planning import build_full_context, plan_next
            from sonya.planning.memory_wiring import record_response_as_memory

            # Fetch recent chat history for context
            session_messages = []
            try:
                me = await userbot._client.get_me()
                my_id = me.id
                recent_msgs = await userbot._client.get_messages(msg_data["chat_id"], limit=12)
                for m in reversed(recent_msgs):
                    if m.text and m.id != msg_data.get("msg_id"):
                        role = "assistant" if m.sender_id == my_id else "user"
                        session_messages.append({"role": role, "content": m.text})
            except Exception as e:
                _log.warning("tg_history_fetch_error", extra={"error": str(e)})

            ctx = build_full_context(
                substrate=substrate,
                user_input=text,
                principal_id=str(msg_data.get("sender_id", "")),
                session_messages=session_messages,
            )
            response = await plan_next(ctx, provider)
            _log.info("tg_response_generated", extra={
                "response_len": len(response.text) if response.text else 0,
                "response_preview": (response.text or "")[:80],
            })
            record_response_as_memory(substrate, text, response, channel="telegram_userbot")
            return response.text if response.text else None
        except Exception as e:
            _log.error("userbot_response_error", extra={"error": str(e), "type": type(e).__name__})
            import traceback
            _log.error("userbot_response_traceback", extra={"tb": traceback.format_exc()})
            return None

    userbot = SonyaUserbot(
        api_id=config.tg_api_id,
        api_hash=config.tg_api_hash,
        session_path=config.tg_session_path.replace(".session", ""),
        on_message=None,  # We register our own handler below
    )

    # Connect and verify authorization (no interactive prompts)
    await userbot._client.connect()
    if not await userbot._client.is_user_authorized():
        _log.error("tg_not_authorized", extra={"event": "session_invalid"})
        return None
    _log.info("tg_authorized", extra={"event": "session_valid"})

    # Track last message time per chat for reply/respond logic
    _last_msg_time: dict[int, float] = {}

    # Register handler with full error handling
    @userbot._client.on(_tg_events.NewMessage(incoming=True))
    async def _tg_handler(event):
        try:
            await event.mark_read()
            msg_data = {
                "chat_id": event.chat_id,
                "sender_id": event.sender_id,
                "text": event.text,
                "date": str(event.date),
                "is_private": event.is_private,
                "reply_to": event.reply_to_msg_id,
                "msg_id": event.id,
            }
            # Show typing while generating response for private messages
            if event.is_private and event.text:
                async with userbot._client.action(event.chat_id, 'typing'):
                    response = await _on_incoming(msg_data)
                if response:
                    # Reply only after >120s pause, otherwise send as new message
                    import time as _time
                    now = _time.time()
                    last = _last_msg_time.get(event.chat_id, 0)
                    if now - last > 120:
                        await event.reply(response)
                    else:
                        await event.respond(response)
                    _last_msg_time[event.chat_id] = now
            else:
                await _on_incoming(msg_data)
        except Exception as e:
            _log.error("tg_handler_crash", extra={"error": str(e), "type": type(e).__name__})
            import traceback
            _log.error("tg_handler_traceback", extra={"tb": traceback.format_exc()})

    # Fetch dialogs to init update state (required for receiving updates)
    dialogs = await userbot._client.get_dialogs(limit=5)
    _log.info("tg_dialogs_loaded", extra={"count": len(dialogs)})

    # Run update loop as background task
    asyncio.create_task(userbot._client.run_until_disconnected())
    userbot._running = True
    _log.info("userbot_started", extra={"event": "userbot_running"})
    return userbot


def _install_signal_handlers(loop: asyncio.AbstractEventLoop, handler) -> None:
    if sys.platform == "win32":
        try:
            signal.signal(signal.SIGINT, lambda *_: handler())
            signal.signal(signal.SIGTERM, lambda *_: handler())
        except (ValueError, OSError):
            pass
        return
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, handler)
        except NotImplementedError:
            signal.signal(sig, lambda *_: handler())


def main(argv: list[str] | None = None) -> int:
    _ = argv if argv is not None else sys.argv[1:]
    config = load_config()
    setup_logging(config.log_level)
    return asyncio.run(_run(config))
