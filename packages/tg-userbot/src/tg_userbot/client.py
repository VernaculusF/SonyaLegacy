"""Telegram Userbot client — Sonya as a user, not a bot.

Uses Telethon (MTProto) for full user-level access:
- Read any chat she's in
- Send messages as herself
- See message history
- React, reply, forward
- No bot API limitations

Requires: api_id + api_hash from https://my.telegram.org
Session file persists login between restarts.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Callable, Awaitable

try:
    from telethon import TelegramClient, events
except ImportError:
    raise ImportError("Install telethon: pip install telethon")


class SonyaUserbot:
    """Telegram userbot — Sonya acts as a real user."""

    def __init__(
        self,
        *,
        api_id: int,
        api_hash: str,
        session_path: str = "sonya_userbot",
        on_message: Callable[[dict[str, Any]], Awaitable[str | None]] | None = None,
    ) -> None:
        self._client = TelegramClient(session_path, api_id, api_hash)
        self._on_message = on_message
        self._running = False

    async def start(self) -> None:
        """Start the userbot. Connects and begins receiving events."""
        await self._client.connect()

        if not await self._client.is_user_authorized():
            raise RuntimeError("Session not authorized. Need a valid .session file.")

        self._running = True

        if self._on_message:
            @self._client.on(events.NewMessage(incoming=True))
            async def _handler(event):
                msg_data = {
                    "chat_id": event.chat_id,
                    "sender_id": event.sender_id,
                    "text": event.text,
                    "date": str(event.date),
                    "is_private": event.is_private,
                    "reply_to": event.reply_to_msg_id,
                }
                response = await self._on_message(msg_data)
                if response:
                    await event.respond(response)

        # Start receiving updates — this keeps the connection alive
        import asyncio
        self._disconnect_future = asyncio.ensure_future(self._client.disconnected)

    async def send_message(self, chat_id: int, text: str) -> None:
        """Send a message to any chat Sonya is in."""
        await self._client.send_message(chat_id, text)

    async def read_history(self, chat_id: int, limit: int = 20) -> list[dict[str, Any]]:
        """Read recent messages from a chat."""
        messages = []
        async for msg in self._client.iter_messages(chat_id, limit=limit):
            messages.append({
                "id": msg.id,
                "sender_id": msg.sender_id,
                "text": msg.text or "",
                "date": str(msg.date),
            })
        return messages

    async def get_dialogs(self, limit: int = 20) -> list[dict[str, Any]]:
        """List recent chats/dialogs."""
        dialogs = []
        async for d in self._client.iter_dialogs(limit=limit):
            dialogs.append({
                "id": d.id,
                "name": d.name,
                "unread_count": d.unread_count,
                "is_user": d.is_user,
                "is_group": d.is_group,
            })
        return dialogs

    async def stop(self) -> None:
        self._running = False
        await self._client.disconnect()

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def client(self) -> TelegramClient:
        return self._client
