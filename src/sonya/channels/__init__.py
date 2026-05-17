"""Channel abstraction — surfaces above the one Sonya subject.

A Channel is a transport-specific adapter (Telegram, Discord, web, voice...)
that translates external events into ChannelMessage objects and delivers
Sonya's responses back through transport-specific APIs.

Architectural rule: the subject above is one Sonya. Channels are surfaces.
See: docs/cognition/CONTINUITY_STREAM_AND_SUBJECT_CORE.md.
"""

from __future__ import annotations

from sonya.channels.base import (
    Channel,
    ChannelDeps,
    ChannelMessage,
    OutgoingMessage,
)
from sonya.channels.registry import ChannelRegistry

__all__ = [
    "Channel",
    "ChannelDeps",
    "ChannelMessage",
    "ChannelRegistry",
    "OutgoingMessage",
]
