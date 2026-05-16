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


def _create_thinking_provider(config: AppConfig):
    """Create a provider for internal thinking loop LLM calls.

    Uses configurable endpoint (SONYA_LLM_API_BASE) and model (SONYA_LLM_MODEL).
    Defaults to OpenRouter. Can point to local proxy, llama.cpp, or any
    OpenAI-compatible endpoint.
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
                        "max_tokens": 500,
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
        idle_interval_seconds=60.0,
        tick_interval_seconds=30.0,
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
        await internal_process.start()
        await health.start(schema_version=substrate.schema_version)
        _log.info(
            "sonya_started",
            extra={
                "event": "started",
                "schema_version": substrate.schema_version,
                "substrate_path": str(config.substrate_path),
            },
        )

        await stop_requested.wait()

        await internal_process.stop()
        await health.stop()
        await lifecycle.request_stop()
        _log.info("sonya_stopped", extra={"event": "stopped"})
        return 0
    finally:
        write_master.release()
        substrate.close()


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
