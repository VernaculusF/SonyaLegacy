from __future__ import annotations

import asyncio
import signal
import sys
from typing import Any

from sonya.channels import (
    Channel,
    ChannelDeps,
    ChannelMessage,
    ChannelRegistry,
    OutgoingMessage,
)
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
from sonya.subject import InternalProcess

_log = get_logger("sonya.main")


def _create_thinking_provider(config: AppConfig):
    """Create a provider for internal thinking loop LLM calls.

    Uses configurable endpoint (SONYA_LLM_API_BASE) and model (SONYA_LLM_MODEL).
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
                        "max_tokens": kwargs.get("max_tokens", 1500),
                        "temperature": kwargs.get("temperature", 0.9),
                        "stream": False,
                    },
                )
                if resp.status_code == 429:
                    _log.warning("provider_rate_limited", extra={"status": 429})
                    return ""
                resp.raise_for_status()
                text = resp.text.strip()
                import json as _json
                try:
                    data = _json.loads(text)
                except _json.JSONDecodeError:
                    first_line = text.split("\n", 1)[0].strip()
                    data = _json.loads(first_line)
                return data["choices"][0]["message"]["content"]

    return _ThinkingProvider()


def _build_incoming_handler(
    *,
    substrate: Substrate,
    internal_process: InternalProcess,
    provider: Any,
    registry: ChannelRegistry,
):
    """Construct the channel-agnostic incoming-message handler.

    The handler:
      1. Records the incoming event in continuity_stream (under
         `incoming.<channel>_message` kind).
      2. Returns a planned OutgoingMessage if planner produced text, or None.

    Per-channel session_messages are pulled from the channel itself when
    available (handlers can read from raw event for transports that support
    chat history fetch — currently only Telegram does).
    """
    async def _on_incoming(msg: ChannelMessage) -> OutgoingMessage | None:
        from sonya.state.continuity_stream import ContinuityEvent, ContinuityStream

        ContinuityStream(substrate).append(ContinuityEvent(
            kind=f"incoming.{msg.channel}_message",
            payload={
                "channel": msg.channel,
                "chat_id": msg.chat_id,
                "sender_id": msg.sender_id,
                "text": (msg.text or "")[:500],
                "media_kind": msg.media_kind,
                "is_private": msg.is_private,
            },
        ))

        if not msg.text:
            return None
        if provider is None:
            _log.warning("no_provider", extra={"channel": msg.channel})
            return None

        try:
            from sonya.planning import build_full_context, plan_next
            from sonya.planning.memory_wiring import record_response_as_memory

            # Per-channel chat history fetch (Telegram supports it via raw event)
            session_messages: list[dict[str, Any]] = []
            if msg.channel == "telegram" and msg.raw is not None:
                try:
                    channel = registry.get("telegram")
                    if channel is not None and hasattr(channel, "_client") and channel._client is not None:
                        client = channel._client
                        my_id = channel._my_id
                        recent = await client.get_messages(int(msg.chat_id), limit=12)
                        for m in reversed(recent):
                            if m.text and (msg.msg_id is None or str(m.id) != msg.msg_id):
                                role = "assistant" if m.sender_id == my_id else "user"
                                session_messages.append({"role": role, "content": m.text})
                except Exception as err:
                    _log.warning("history_fetch_error", extra={"error": str(err)})

            ctx = build_full_context(
                substrate=substrate,
                user_input=msg.text,
                principal_id=msg.sender_id,
                session_messages=session_messages,
            )
            response = await plan_next(ctx, provider)
            _log.info(
                "response_generated",
                extra={
                    "channel": msg.channel,
                    "response_len": len(response.text) if response.text else 0,
                    "preview": (response.text or "")[:80],
                },
            )
            record_response_as_memory(
                substrate, msg.text, response, channel=f"{msg.channel}_userbot"
            )
            if response.text:
                return OutgoingMessage(text=response.text)
            return None
        except Exception as err:
            _log.error(
                "response_error",
                extra={"channel": msg.channel, "error": str(err), "type": type(err).__name__},
            )
            import traceback
            _log.error("response_traceback", extra={"tb": traceback.format_exc()})
            return None

    return _on_incoming


def _build_channels(config: AppConfig) -> list[Channel]:
    """Construct configured channel adapters. Add new channels here.

    For Sonya-authored channels (via selfmod), they live in src/sonya/channels/
    and can be hot-imported here once added (after process restart in MVP).
    """
    channels: list[Channel] = []

    if config.enable_telegram and config.tg_api_id and config.tg_session_path:
        try:
            from sonya.channels.telegram import TelegramChannel
            channels.append(TelegramChannel(
                api_id=config.tg_api_id,
                api_hash=config.tg_api_hash,
                session_path=config.tg_session_path,
            ))
        except ImportError as err:
            _log.warning(
                "telegram_channel_unavailable",
                extra={"error": str(err)},
            )

    return channels


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

    raw_stream = ContinuityStream(substrate)
    raw_state_store = SubjectStateStore(substrate)
    intention_store = PendingIntentionStore(substrate)

    thinking_provider = _create_thinking_provider(config)
    internal_process = InternalProcess(
        stream=raw_stream,
        intention_store=intention_store,
        substrate=substrate,
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

    # Channel layer
    registry = ChannelRegistry()
    for channel in _build_channels(config):
        registry.register(channel)

    handler = _build_incoming_handler(
        substrate=substrate,
        internal_process=internal_process,
        provider=thinking_provider,
        registry=registry,
    )
    deps = ChannelDeps(
        on_incoming=lambda msg: _wrapped_handler(msg, handler, internal_process),
        notify_external_event=internal_process.notify_external_event,
        config=config,
        substrate=substrate,
    )

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

        if registry.list_names():
            await registry.start_all(deps)
        else:
            _log.info("no_channels_configured")

        await health.start(schema_version=substrate.schema_version)
        _log.info(
            "sonya_started",
            extra={
                "event": "started",
                "schema_version": substrate.schema_version,
                "substrate_path": str(config.substrate_path),
                "channels": registry.list_names(),
                "thinking": "enabled" if config.enable_thinking else "disabled",
            },
        )

        await stop_requested.wait()

        await registry.stop_all()
        if config.enable_thinking:
            await internal_process.stop()
        await health.stop()
        await lifecycle.request_stop()
        _log.info("sonya_stopped", extra={"event": "stopped"})
        return 0
    finally:
        write_master.release()
        substrate.close()


async def _wrapped_handler(
    msg: ChannelMessage,
    handler,
    internal_process: InternalProcess,
) -> OutgoingMessage | None:
    """Tiny wrapper that always notifies internal_process before delegating."""
    internal_process.notify_external_event()
    return await handler(msg)


def _install_signal_handlers(loop: asyncio.AbstractEventLoop, handler) -> None:
    if sys.platform == "win32":
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                signal.signal(sig, lambda *_: handler())
            except (ValueError, OSError) as err:
                _log.warning("signal_install_failed", extra={"sig": sig.name, "error": str(err)})
        return
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, handler)
        except NotImplementedError:
            try:
                signal.signal(sig, lambda *_: handler())
            except (ValueError, OSError) as err:
                _log.warning("signal_install_failed", extra={"sig": sig.name, "error": str(err)})


def main(argv: list[str] | None = None) -> int:
    _ = argv if argv is not None else sys.argv[1:]
    config = load_config()
    setup_logging(config.log_level)
    return asyncio.run(_run(config))
