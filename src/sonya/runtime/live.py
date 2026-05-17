"""LiveRuntime — global handle to running subsystems for hot-reload.

When selfmod applies changes, it needs to drop-and-recreate live instances
(channels, internal_process, etc.) to pick up the new code. This module
holds the global handles set by main.py at startup.

Single instance per process. Modules call `set_live_runtime(...)` once,
and selfmod_tool reads it via `get_live_runtime()`.

Not part of `state/` because this is process-state, not subject-state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class LiveRuntime:
    """Handles to currently-running subsystem instances.

    All fields optional so tests / partial setups work.
    """

    channel_registry: Any = None  # sonya.channels.ChannelRegistry
    channel_deps: Any = None  # sonya.channels.ChannelDeps
    internal_process: Any = None  # sonya.subject.InternalProcess
    substrate: Any = None  # sonya.state.Substrate
    config: Any = None  # sonya.config.AppConfig
    provider: Any = None  # thinking provider (LLM)
    handler_factory: Any = None  # callable producing on_incoming handler
    deps_factory: Any = None  # callable producing ChannelDeps
    extras: dict[str, Any] = field(default_factory=dict)


_live: LiveRuntime | None = None


def set_live_runtime(runtime: LiveRuntime) -> None:
    global _live
    _live = runtime


def get_live_runtime() -> LiveRuntime | None:
    return _live


def clear_live_runtime() -> None:
    global _live
    _live = None
