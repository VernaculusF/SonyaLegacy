"""Telegram tool for agent sessions — Sonya can read/send via userbot."""

from __future__ import annotations

from typing import Any

from tg_userbot.client import SonyaUserbot


class TelegramTool:
    """Tool interface for agent sessions to interact with Telegram.

    Used by agent_session when Sonya wants to:
    - Check her inbox
    - Read chat history
    - Send a message to someone
    - List her chats
    """

    def __init__(self, userbot: SonyaUserbot) -> None:
        self._bot = userbot

    async def read_inbox(self, limit: int = 10) -> str:
        """List recent dialogs with unread counts."""
        dialogs = await self._bot.get_dialogs(limit=limit)
        if not dialogs:
            return "No dialogs found."
        lines = []
        for d in dialogs:
            unread = f" ({d['unread_count']} unread)" if d['unread_count'] else ""
            lines.append(f"- {d['name']} [id={d['id']}]{unread}")
        return "\n".join(lines)

    async def read_chat(self, chat_id: int, limit: int = 15) -> str:
        """Read recent messages from a specific chat."""
        messages = await self._bot.read_history(chat_id, limit=limit)
        if not messages:
            return "No messages."
        lines = []
        for m in reversed(messages):
            sender = f"[{m['sender_id']}]"
            lines.append(f"{m['date'][:16]} {sender}: {m['text'][:200]}")
        return "\n".join(lines)

    async def send_message(self, chat_id: int, text: str) -> str:
        """Send a message to a chat."""
        await self._bot.send_message(chat_id, text)
        return f"[OK] Message sent to {chat_id}"
