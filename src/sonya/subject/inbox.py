"""Per-chat message inbox.

When Ivan sends multiple messages in quick succession, the second one might
arrive while Sonya is still processing the first. Without coordination, that
message either:
  (a) starts a parallel agent session — wastes tokens, fights for the same DB
      slot, garbled responses
  (b) gets dropped if the channel handler refuses
  (c) is processed sequentially with full latency

Inbox approach: per-chat asyncio.Lock around session execution. New messages
arriving during a running session are queued. The running agent_session
checks the inbox between steps and, if there's anything, injects it as a
user turn so the model can read and react mid-flight (cancel task, answer
quickly via chat.tell_ivan, ignore in favor of current task).

This is the closest we can get to "human reads the new message while still
working" without continuous state.
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Deque


@dataclass(slots=True)
class InboxItem:
    text: str
    received_at: float = field(default_factory=time.time)
    sender_id: str = ""


class MessageInbox:
    """Per-chat queue + lock. Singleton lives in main app state."""

    def __init__(self) -> None:
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._queues: dict[str, Deque[InboxItem]] = defaultdict(deque)

    def lock_for(self, chat_id: str) -> asyncio.Lock:
        return self._locks[chat_id]

    def push(self, chat_id: str, item: InboxItem) -> None:
        self._queues[chat_id].append(item)

    def drain(self, chat_id: str) -> list[InboxItem]:
        """Pop everything currently queued for this chat."""
        q = self._queues.get(chat_id)
        if not q:
            return []
        items = list(q)
        q.clear()
        return items

    def has_pending(self, chat_id: str) -> bool:
        q = self._queues.get(chat_id)
        return bool(q)
