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
from sonya.state import Substrate, SubstrateVersionError, seed_identity_if_empty

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
