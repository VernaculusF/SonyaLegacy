"""Channel Protocol — shared interface for all surfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class ChannelMessage:
    """Normalized incoming message from any channel."""

    channel: str  # "telegram", "discord", etc.
    chat_id: str  # transport-specific chat identifier (str for portability)
    sender_id: str  # transport-specific sender identifier
    text: str  # text content or human-readable description (e.g. "[стикер 😏]")
    is_private: bool  # 1:1 chat (True) vs group (False)
    media_kind: str | None = None  # "фото", "стикер", "голосовое сообщение", etc.
    media_path: str | None = None  # absolute path to downloaded media file, when available
    media_mime: str | None = None  # MIME type of downloaded media (e.g. "image/jpeg")
    reply_to_id: str | None = None  # transport-specific id of replied-to message
    msg_id: str | None = None  # transport-specific id of this message
    raw: Any = None  # transport-specific event object for advanced handlers


@dataclass(frozen=True, slots=True)
class OutgoingMessage:
    """Sonya's response to be delivered through a channel."""

    text: str
    reply_to_id: str | None = None  # if set, transport will use reply semantics
    media_kind: str | None = None  # for future TTS / image attachment
    sticker_emoji: str | None = None  # if set, channel will send a sticker matching this emoji


# Callback signature: channel hands incoming message + optional response sender to deps
IncomingHandler = Callable[[ChannelMessage], Awaitable[OutgoingMessage | None]]


@dataclass(slots=True)
class ChannelDeps:
    """Dependencies injected into channels at start time.

    The composition root (main.py) provides these so channels don't need to
    know about substrate, internal_process, or planner directly.
    """

    on_incoming: IncomingHandler  # channel calls this with ChannelMessage; gets back OutgoingMessage or None
    notify_external_event: Callable[[], None] = lambda: None  # reset idle timers etc.
    config: Any = None  # AppConfig (typed loosely to avoid import cycle)
    substrate: Any = None  # Substrate (same reason)
    extra: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class Channel(Protocol):
    """Stable interface every channel adapter must satisfy.

    Lifecycle:
      1. registry.register(channel)  — ChannelRegistry stores it
      2. await channel.start(deps)   — channel connects, registers handlers
      3. (channel runs, calls deps.on_incoming on each new message)
      4. await channel.send(target, OutgoingMessage)  — Sonya pushes message out
      5. await channel.stop()        — graceful shutdown

    Channels are responsible for:
      - translating transport events into ChannelMessage
      - calling deps.on_incoming and delivering the OutgoingMessage if returned
      - exposing a send() for initiative (Sonya writes first)
      - clean shutdown
    """

    name: str  # unique identifier ("telegram", "discord", ...)

    async def start(self, deps: ChannelDeps) -> None:
        """Connect and start receiving. Must be idempotent if already started."""
        ...

    async def stop(self) -> None:
        """Graceful shutdown. Must be safe to call multiple times."""
        ...

    async def send(self, chat_id: str, message: OutgoingMessage) -> None:
        """Push a message out — used by initiative path."""
        ...

    @property
    def is_running(self) -> bool:
        """Quick liveness check for admin panel."""
        ...
