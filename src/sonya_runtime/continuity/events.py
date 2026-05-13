from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ContinuityEvent:
    event_type: str
    principal_id: str
    origin_channel: str
    origin_chat_id: str
    source_message: str
