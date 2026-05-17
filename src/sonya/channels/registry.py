"""Channel registry — manages lifecycle of multiple channels."""

from __future__ import annotations

import asyncio
from typing import Iterable

from sonya.channels.base import Channel, ChannelDeps, OutgoingMessage
from sonya.logging import get_logger

_log = get_logger("sonya.channels.registry")


class ChannelRegistryError(RuntimeError):
    pass


class ChannelRegistry:
    """Holds Channel instances, starts/stops them, routes outbound messages.

    Hot-add and hot-remove supported — Sonya can register a freshly-applied
    channel module without restart (provided the module is importable; for
    selfmod-applied changes a process restart is currently still required).
    """

    def __init__(self) -> None:
        self._channels: dict[str, Channel] = {}
        self._deps: ChannelDeps | None = None
        self._lock = asyncio.Lock()

    def register(self, channel: Channel) -> None:
        """Register a channel. If already registered, raises."""
        if channel.name in self._channels:
            raise ChannelRegistryError(f"channel '{channel.name}' already registered")
        self._channels[channel.name] = channel
        _log.info("channel_registered", extra={"channel": channel.name})

    def unregister(self, name: str) -> None:
        """Remove a channel from registry (does NOT stop it — call stop() first)."""
        self._channels.pop(name, None)

    def get(self, name: str) -> Channel | None:
        return self._channels.get(name)

    def list_names(self) -> list[str]:
        return list(self._channels.keys())

    def all(self) -> Iterable[Channel]:
        return self._channels.values()

    async def start_all(self, deps: ChannelDeps) -> None:
        """Start every registered channel. Failures are logged but don't abort siblings."""
        async with self._lock:
            self._deps = deps
            for name, channel in self._channels.items():
                try:
                    await channel.start(deps)
                    _log.info("channel_started", extra={"channel": name})
                except Exception as err:
                    _log.error(
                        "channel_start_failed",
                        extra={"channel": name, "error": str(err), "type": type(err).__name__},
                    )

    async def start_one(self, name: str) -> bool:
        """Start a single channel by name. Returns True if started."""
        async with self._lock:
            channel = self._channels.get(name)
            if channel is None or self._deps is None:
                return False
            try:
                await channel.start(self._deps)
                return True
            except Exception as err:
                _log.error(
                    "channel_start_failed",
                    extra={"channel": name, "error": str(err)},
                )
                return False

    async def stop_all(self) -> None:
        """Stop every running channel."""
        async with self._lock:
            for name, channel in self._channels.items():
                try:
                    await channel.stop()
                    _log.info("channel_stopped", extra={"channel": name})
                except Exception as err:
                    _log.error(
                        "channel_stop_failed",
                        extra={"channel": name, "error": str(err)},
                    )

    async def send(self, channel_name: str, chat_id: str, message: OutgoingMessage) -> bool:
        """Send a message through a specific channel. Returns True on success."""
        channel = self._channels.get(channel_name)
        if channel is None or not channel.is_running:
            _log.warning(
                "send_failed_channel_unavailable",
                extra={"channel": channel_name},
            )
            return False
        try:
            await channel.send(chat_id, message)
            return True
        except Exception as err:
            _log.error(
                "send_failed",
                extra={"channel": channel_name, "error": str(err), "type": type(err).__name__},
            )
            return False

    def status(self) -> list[dict]:
        """Snapshot of registry state for admin panel."""
        return [
            {"name": ch.name, "running": ch.is_running}
            for ch in self._channels.values()
        ]
