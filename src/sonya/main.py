from __future__ import annotations

import asyncio
import importlib
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
    LiveRuntime,
    WriteMaster,
    WriteMasterContention,
    set_live_runtime,
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


def _create_thinking_provider(config: AppConfig, substrate: "Substrate"):
    """Create a substrate-backed LLM provider with key rotation.

    Replaces the legacy single-key OmniRoute path. All keys live in
    `provider_keys` table, manageable through admin UI. The active provider
    + default model are in `provider_settings` row.

    If no keys are configured, returns None (Sonya runs without LLM).
    """
    from sonya.providers import KeyStore, LLMProvider

    store = KeyStore(substrate)
    settings = store.get_settings()
    keys = [k for k in store.list_keys(settings.active_provider) if k.status.value == "active"]
    if not keys:
        _log.warning(
            "no_provider_keys",
            extra={
                "event": "thinking_provider_disabled",
                "provider": settings.active_provider,
                "hint": "Add keys via admin → Providers tab",
            },
        )
        return None

    _log.info(
        "thinking_provider_ready",
        extra={
            "provider": settings.active_provider,
            "default_model": settings.default_model,
            "active_keys": len(keys),
        },
    )
    return LLMProvider(store)

    return _ThinkingProvider()


def _build_incoming_handler(
    *,
    substrate: Substrate,
    internal_process: InternalProcess,
    provider: Any,
    registry: ChannelRegistry,
):
    """Construct the channel-agnostic incoming-message handler."""
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
                drives=internal_process.drives if internal_process else None,
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
    """Auto-discover and construct configured channel adapters.

    Sweeps `src/sonya/channels/*.py` (excluding base/registry/__init__) and
    looks for top-level `build(config) -> Channel | None` factory function.

    Sonya can add a new channel by writing one file under
    `src/sonya/channels/discord.py` containing `def build(config): ...` —
    soft-restart picks it up without main.py changes.
    """
    from pathlib import Path

    channels_dir = Path(__file__).parent / "channels"
    skip = {"__init__.py", "base.py", "registry.py"}

    channels: list[Channel] = []
    for py_file in sorted(channels_dir.glob("*.py")):
        if py_file.name in skip:
            continue
        dotted = f"sonya.channels.{py_file.stem}"
        try:
            # Force re-import so newly-applied changes pick up
            if dotted in sys.modules:
                module = importlib.reload(sys.modules[dotted])
            else:
                module = importlib.import_module(dotted)
        except Exception as err:
            _log.warning(
                "channel_module_import_failed",
                extra={"channel_module": dotted, "error": str(err)},
            )
            continue

        build_fn = getattr(module, "build", None)
        if callable(build_fn):
            try:
                instance = build_fn(config)
            except Exception as err:
                _log.warning(
                    "channel_build_failed",
                    extra={"channel_module": dotted, "error": str(err)},
                )
                continue
            if instance is not None:
                channels.append(instance)
                _log.info(
                    "channel_built",
                    extra={"channel_module": dotted, "channel_name": getattr(instance, "name", "?")},
                )
            continue

        _log.debug(
            "channel_module_no_build_factory",
            extra={"channel_module": dotted, "hint": "add `def build(config): ...` to register"},
        )

    return channels


# ---------- Runtime task: builds, runs, tears down ----------


class _RuntimeBundle:
    """Group of subsystems that compose the inner runtime loop.

    The supervisor builds/tears down this bundle on soft-restart.
    Substrate + WriteMaster + admin live OUTSIDE the bundle, so they
    survive restarts.
    """

    def __init__(
        self,
        *,
        substrate: Substrate,
        config: AppConfig,
        bus: EventBus,
    ) -> None:
        self.substrate = substrate
        self.config = config
        self.bus = bus
        self.lifecycle: Lifecycle | None = None
        self.health: Health | None = None
        self.internal_process: InternalProcess | None = None
        self.channel_registry: ChannelRegistry | None = None
        self.thinking_provider: Any = None

    async def start(self) -> None:
        config = self.config
        substrate = self.substrate

        if seed_identity_if_empty(substrate):
            _log.info(
                "identity_seeded",
                extra={"event": "identity_seeded", "change_id": "identity-seed"},
            )

        raw_stream = ContinuityStream(substrate)
        intention_store = PendingIntentionStore(substrate)

        self.thinking_provider = _create_thinking_provider(config, substrate)
        self.internal_process = InternalProcess(
            stream=raw_stream,
            intention_store=intention_store,
            substrate=substrate,
            provider=self.thinking_provider,
            thinking_prompt=(
                "Ты Соня. Это твой внутренний поток мышления. "
                "Никто не читает это кроме тебя. "
                "Подумай о чём хочешь — о себе, об Иване, о том что делала, о том что хочешь."
            ),
            idle_interval_seconds=1800.0,   # 30 минут — idle thinking tick
            tick_interval_seconds=60.0,
            active_interval_seconds=7200.0,  # 2 часа — active session с tools (экономим лимиты)
        )

        self.lifecycle = Lifecycle(substrate=substrate, event_bus=self.bus)
        self.health = Health(path=config.health_path)

        # Channel layer
        self.channel_registry = ChannelRegistry()
        for channel in _build_channels(config):
            self.channel_registry.register(channel)

        # Этап D: outbound initiative gate
        if config.primary_user_tg_id:
            from sonya.initiative.outbound import OutboundGate
            outbound = OutboundGate(
                registry=self.channel_registry,
                stream=raw_stream,
                target_tg_chat_id=config.primary_user_tg_id,
                max_per_day=config.initiative_max_per_day,
                min_quiet_minutes=config.initiative_min_quiet_minutes,
            )
            self.internal_process.set_outbound_gate(outbound)
            _log.info(
                "initiative_enabled",
                extra={
                    "target": config.primary_user_tg_id,
                    "max_per_day": config.initiative_max_per_day,
                    "min_quiet_minutes": config.initiative_min_quiet_minutes,
                },
            )
        else:
            _log.info("initiative_disabled", extra={"reason": "SONYA_PRIMARY_USER_TG_ID not set"})

        handler = _build_incoming_handler(
            substrate=substrate,
            internal_process=self.internal_process,
            provider=self.thinking_provider,
            registry=self.channel_registry,
        )
        ip = self.internal_process

        def _wrap_handler(msg: ChannelMessage):
            ip.notify_external_event()
            return handler(msg)

        deps = ChannelDeps(
            on_incoming=_wrap_handler,
            notify_external_event=self.internal_process.notify_external_event,
            config=config,
            substrate=substrate,
        )

        # Register live runtime for selfmod hot-reload + soft-restart
        live = LiveRuntime(
            channel_registry=self.channel_registry,
            channel_deps=deps,
            internal_process=self.internal_process,
            substrate=substrate,
            config=config,
            provider=self.thinking_provider,
        )
        # Add restart_event so selfmod can request soft-restart
        live.extras["restart_event"] = asyncio.Event()
        set_live_runtime(live)

        # Start subsystems
        await self.lifecycle.start()
        if config.enable_thinking:
            await self.internal_process.start()
            _log.info("thinking_enabled")
        else:
            _log.info("thinking_disabled")

        if self.channel_registry.list_names():
            await self.channel_registry.start_all(deps)
        else:
            _log.info("no_channels_configured")

        await self.health.start(schema_version=substrate.schema_version)

    async def stop(self) -> None:
        if self.channel_registry is not None:
            try:
                await self.channel_registry.stop_all()
            except Exception as err:
                _log.warning("registry_stop_error", extra={"error": str(err)})
        if self.internal_process is not None and self.config.enable_thinking:
            try:
                await self.internal_process.stop()
            except Exception as err:
                _log.warning("internal_stop_error", extra={"error": str(err)})
        if self.health is not None:
            try:
                await self.health.stop()
            except Exception as err:
                _log.warning("health_stop_error", extra={"error": str(err)})
        if self.lifecycle is not None:
            try:
                await self.lifecycle.request_stop()
            except Exception as err:
                _log.warning("lifecycle_stop_error", extra={"error": str(err)})


async def _supervisor(config: AppConfig) -> int:
    """Outer supervisor — keeps substrate + write-master alive across runtime restarts.

    Runtime bundle (channels/internal_process/health/lifecycle) can be torn down
    and rebuilt on soft-restart without releasing the write-master or closing
    substrate. selfmod_tool sets `live.extras['restart_event']` to trigger.
    """
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

    bus = EventBus()
    loop = asyncio.get_running_loop()
    stop_requested = asyncio.Event()

    def _on_signal(*_: Any) -> None:
        _log.info("signal_received", extra={"event": "shutdown_requested"})
        stop_requested.set()

    _install_signal_handlers(loop, _on_signal)

    restart_count = 0

    try:
        while not stop_requested.is_set():
            bundle = _RuntimeBundle(substrate=substrate, config=config, bus=bus)
            try:
                await bundle.start()
            except Exception as err:
                _log.error(
                    "runtime_start_failed",
                    extra={"error": str(err), "type": type(err).__name__},
                )
                # If first start fails, give up. On restart attempt, log + retry once.
                if restart_count == 0:
                    return 4
                _log.warning("retrying_in_5s")
                await asyncio.sleep(5.0)
                continue

            from sonya.runtime.live import get_live_runtime
            live = get_live_runtime()
            restart_event: asyncio.Event = (
                live.extras.get("restart_event")
                if live and live.extras.get("restart_event")
                else asyncio.Event()
            )

            _log.info(
                "sonya_started",
                extra={
                    "event": "started",
                    "schema_version": substrate.schema_version,
                    "substrate_path": str(config.substrate_path),
                    "channels": (
                        bundle.channel_registry.list_names()
                        if bundle.channel_registry else []
                    ),
                    "thinking": "enabled" if config.enable_thinking else "disabled",
                    "restart_count": restart_count,
                },
            )

            # Wait for either stop or restart
            stop_task = asyncio.create_task(stop_requested.wait())
            restart_task = asyncio.create_task(restart_event.wait())
            done, pending = await asyncio.wait(
                {stop_task, restart_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for t in pending:
                t.cancel()

            await bundle.stop()

            if stop_requested.is_set():
                _log.info("sonya_stopped", extra={"event": "stopped"})
                break

            # Soft restart path
            restart_count += 1
            _log.info(
                "sonya_soft_restart",
                extra={"restart_count": restart_count, "reason": "selfmod_request"},
            )
            # Reload core modules so new code is picked up by next bundle.start()
            _reload_core_modules()
            # Tiny pause to let any pending writes flush
            await asyncio.sleep(0.5)

        return 0
    finally:
        write_master.release()
        substrate.close()


def _reload_core_modules() -> None:
    """Reload modules that the runtime bundle imports.

    Called on soft-restart so a freshly-applied change to e.g.
    `src/sonya/main.py` _build_channels function takes effect.

    Order matters: dependencies first. We reload bottom-up.
    """
    targets = [
        # Tools — selfmod might have changed any of these
        "sonya.tools.module_loader",
        "sonya.tools.filesystem",
        "sonya.tools.self_inspect",
        "sonya.tools.selfmod_tool",
        "sonya.tools",
        # Channels base
        "sonya.channels.base",
        "sonya.channels.registry",
        "sonya.channels",
        # Planning / memory might have changed
        "sonya.planning.context_builder",
        "sonya.planning.planner",
        "sonya.planning",
        "sonya.memory.episodic",
        "sonya.memory.semantic",
        "sonya.memory",
        # Subject layer
        "sonya.subject.agent_session",
        "sonya.subject.internal_loop",
        "sonya.subject",
    ]
    for dotted in targets:
        if dotted in sys.modules:
            try:
                importlib.reload(sys.modules[dotted])
            except Exception as err:
                _log.warning(
                    "module_reload_failed",
                    extra={"target_module": dotted, "error": str(err)},
                )


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
    return asyncio.run(_supervisor(config))
