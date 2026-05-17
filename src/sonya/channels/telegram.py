"""Telegram channel via tg_userbot (Telethon).

Implements Channel Protocol. Translates Telegram events to ChannelMessage,
delivers OutgoingMessage back through Telethon. Handles media detection,
group addressing rules, reply-vs-respond logic.

Logic ported from src/sonya/main.py inline handler (commits 6e6f305 + 0e3314b).
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from sonya.channels.base import Channel, ChannelDeps, ChannelMessage, OutgoingMessage
from sonya.logging import get_logger

_log = get_logger("sonya.channels.telegram")


class TelegramChannel:
    """Telegram userbot channel."""

    name = "telegram"

    def __init__(
        self,
        *,
        api_id: int,
        api_hash: str,
        session_path: str,
        allowed_sender_ids: tuple[str, ...] = (),
    ) -> None:
        self._api_id = api_id
        self._api_hash = api_hash
        # Telethon strips .session if present; pass the path without it
        self._session_path = session_path.replace(".session", "")
        self._client: Any = None
        self._run_task: asyncio.Task | None = None
        self._running = False
        self._my_id: int | None = None
        self._my_username: str = ""
        self._my_first_name: str = ""
        # Per-chat last outgoing-time tracker for reply/respond logic
        self._last_msg_time: dict[int, float] = {}
        self._deps: ChannelDeps | None = None
        # Sender allowlist for private DMs. Empty = open to anyone (legacy mode).
        # When non-empty, only listed sender_ids get a planner-generated response;
        # others are logged and ignored. Group chats unaffected (use addressing).
        self._allowed_senders: set[str] = {s for s in allowed_sender_ids if s}

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self, deps: ChannelDeps) -> None:
        if self._running:
            return
        try:
            from telethon import TelegramClient, events
            from telethon.tl.types import (
                MessageMediaPhoto,
                MessageMediaDocument,
                DocumentAttributeSticker,
                DocumentAttributeAudio,
                DocumentAttributeVideo,
                DocumentAttributeAnimated,
            )
        except ImportError as err:
            raise ImportError("telethon not installed: pip install telethon") from err

        self._deps = deps
        self._client = TelegramClient(self._session_path, self._api_id, self._api_hash)

        await self._client.connect()
        if not await self._client.is_user_authorized():
            _log.error("tg_not_authorized")
            raise RuntimeError("Telegram session not authorized")
        _log.info("tg_authorized")

        me = await self._client.get_me()
        self._my_id = me.id
        self._my_username = (me.username or "").lower()
        self._my_first_name = (me.first_name or "").lower()
        _log.info(
            "tg_self_info",
            extra={"id": self._my_id, "username": self._my_username},
        )

        # Capture local refs for closure
        client = self._client
        my_id = self._my_id
        my_username = self._my_username
        my_first_name = self._my_first_name
        last_msg_time = self._last_msg_time

        def _detect_media_kind(event) -> str | None:
            msg = event.message
            if not msg or not msg.media:
                return None
            media = msg.media
            if isinstance(media, MessageMediaPhoto):
                return "фото"
            if isinstance(media, MessageMediaDocument) and media.document:
                doc = media.document
                attrs = doc.attributes or []
                for attr in attrs:
                    if isinstance(attr, DocumentAttributeSticker):
                        emoji = getattr(attr, "alt", "") or ""
                        return f"стикер {emoji}".strip()
                    if isinstance(attr, DocumentAttributeAudio):
                        return "голосовое сообщение" if attr.voice else "аудио"
                    if isinstance(attr, DocumentAttributeAnimated):
                        return "гифка"
                    if isinstance(attr, DocumentAttributeVideo):
                        return "видеосообщение" if attr.round_message else "видео"
                return "файл"
            return "медиа"

        async def _should_respond_in_group(event, text: str) -> bool:
            if not text:
                return False
            text_lower = text.lower()
            if my_username and f"@{my_username}" in text_lower:
                return True
            if my_first_name and text_lower.startswith(my_first_name):
                return True
            if event.reply_to_msg_id:
                try:
                    replied = await event.get_reply_message()
                    if replied and replied.sender_id == my_id:
                        return True
                except Exception:
                    pass
            return False

        @client.on(events.NewMessage(incoming=True))
        async def _handler(event):
            try:
                await event.mark_read()
                text = event.text or ""
                media_kind = _detect_media_kind(event)
                if not text and media_kind:
                    text = f"[{media_kind}]"

                msg = ChannelMessage(
                    channel=self.name,
                    chat_id=str(event.chat_id),
                    sender_id=str(event.sender_id),
                    text=text,
                    is_private=event.is_private,
                    media_kind=media_kind,
                    reply_to_id=str(event.reply_to_msg_id) if event.reply_to_msg_id else None,
                    msg_id=str(event.id),
                    raw=event,
                )

                _log.info(
                    "tg_incoming",
                    extra={
                        "chat_id": msg.chat_id,
                        "sender_id": msg.sender_id,
                        "text_preview": msg.text[:80],
                        "media_kind": msg.media_kind,
                        "is_private": msg.is_private,
                    },
                )

                # External event signal (resets idle counters etc.)
                deps.notify_external_event()

                # Decide whether to invoke planner (i.e., generate a response)
                should_respond = False
                if event.is_private and text:
                    # Allowlist gate: when configured, only respond to whitelisted
                    # sender_ids in private DMs. Stops randoms from triggering
                    # LLM calls (token waste + identity leak through generic replies).
                    if self._allowed_senders and msg.sender_id not in self._allowed_senders:
                        _log.info(
                            "tg_unauthorized_private_dm",
                            extra={
                                "sender_id": msg.sender_id,
                                "chat_id": msg.chat_id,
                                "text_preview": msg.text[:80],
                                "allowed": sorted(self._allowed_senders),
                            },
                        )
                        should_respond = False
                    else:
                        should_respond = True
                elif text and not event.is_private:
                    should_respond = await _should_respond_in_group(event, text)
                    if should_respond:
                        _log.info("tg_group_address_detected", extra={"chat_id": msg.chat_id})

                if should_respond:
                    async with client.action(event.chat_id, "typing"):
                        response = await deps.on_incoming(msg)
                    if response and response.text:
                        now = time.time()
                        last = last_msg_time.get(event.chat_id, 0)
                        # In groups always reply (clarity); in private use 120s pause heuristic
                        if not event.is_private or now - last > 120:
                            await event.reply(response.text)
                        else:
                            await event.respond(response.text)
                        last_msg_time[event.chat_id] = now
                else:
                    # Still notify so handler can record/track without generating response
                    await deps.on_incoming(msg)
            except Exception as err:
                _log.error(
                    "tg_handler_crash",
                    extra={"error": str(err), "type": type(err).__name__},
                )
                import traceback as _tb
                _log.error("tg_handler_traceback", extra={"tb": _tb.format_exc()})

        # Force fetch dialogs to init update state
        dialogs = await client.get_dialogs(limit=5)
        _log.info("tg_dialogs_loaded", extra={"count": len(dialogs)})

        self._run_task = asyncio.create_task(client.run_until_disconnected())
        self._running = True
        _log.info("tg_channel_started")

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._run_task is not None:
            self._run_task.cancel()
            try:
                await asyncio.wait_for(self._run_task, timeout=3.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
            self._run_task = None
        if self._client is not None:
            try:
                await self._client.disconnect()
            except Exception:
                pass
        _log.info("tg_channel_stopped")

    async def send(self, chat_id: str, message: OutgoingMessage) -> None:
        """Outbound message — used by initiative path or admin commands."""
        if not self._running or self._client is None:
            raise RuntimeError("telegram channel not running")
        try:
            tg_chat_id = int(chat_id)
        except ValueError as err:
            raise ValueError(f"telegram chat_id must be int-compatible, got: {chat_id}") from err
        if message.reply_to_id:
            try:
                reply_to = int(message.reply_to_id)
                await self._client.send_message(
                    tg_chat_id, message.text, reply_to=reply_to
                )
                return
            except (ValueError, TypeError):
                pass  # fall through to non-reply send
        await self._client.send_message(tg_chat_id, message.text)
        self._last_msg_time[tg_chat_id] = time.time()


def build(config: Any) -> "TelegramChannel | None":
    """Auto-discovery factory for main._build_channels.

    Returns a TelegramChannel if Telegram is enabled and credentials are present,
    else None (channel is silently skipped).
    """
    if not getattr(config, "enable_telegram", True):
        return None
    api_id = getattr(config, "tg_api_id", 0)
    if not api_id:
        return None
    primary_user = str(getattr(config, "primary_user_tg_id", "") or "").strip()
    extras_raw = str(getattr(config, "tg_allowed_extra_senders", "") or "").strip()
    extras = tuple(s.strip() for s in extras_raw.split(",") if s.strip())
    allowed = tuple([primary_user] + list(extras)) if primary_user else extras
    return TelegramChannel(
        api_id=api_id,
        api_hash=getattr(config, "tg_api_hash", ""),
        session_path=getattr(config, "tg_session_path", "./tg.session"),
        allowed_sender_ids=allowed,
    )
