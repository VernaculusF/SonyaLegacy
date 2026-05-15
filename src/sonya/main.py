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

    # Internal cognitive process
    internal_process = InternalProcess(
        stream=raw_stream,
        intention_store=intention_store,
        idle_interval_seconds=300.0,
        tick_interval_seconds=10.0,
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
