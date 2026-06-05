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
        media_dir: str | None = None,
        sticker_store: Any = None,
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
        # Where to download incoming media. None disables download (text-only mode).
        self._media_dir: str | None = media_dir
        if self._media_dir:
            from pathlib import Path as _Path
            _Path(self._media_dir).mkdir(parents=True, exist_ok=True)
        # Optional sticker store for capture+resend (StickerStore from sticker_store.py).
        self._sticker_store = sticker_store

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self, deps: ChannelDeps) -> None:
        if self._running:
            return
        try:
            from telethon import TelegramClient, events
            from telethon.errors import AuthKeyDuplicatedError, RPCError
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

        try:
            await self._client.connect()
            authorized = await self._client.is_user_authorized()
        except AuthKeyDuplicatedError as err:
            _log.error(
                "tg_session_invalidated",
                extra={"error": str(err), "action": "stop duplicate Telegram session and re-login"},
            )
            raise RuntimeError("Telegram session invalidated by simultaneous use from another IP") from err
        if not authorized:
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
                # Two-pass: sticker attribute takes priority (video stickers
                # have both DocumentAttributeSticker + DocumentAttributeVideo)
                has_sticker = False
                sticker_emoji = ""
                has_video = False
                is_round = False
                has_audio = False
                is_voice = False
                has_animated = False
                for attr in attrs:
                    if isinstance(attr, DocumentAttributeSticker):
                        has_sticker = True
                        sticker_emoji = getattr(attr, "alt", "") or ""
                    elif isinstance(attr, DocumentAttributeVideo):
                        has_video = True
                        is_round = getattr(attr, "round_message", False)
                    elif isinstance(attr, DocumentAttributeAudio):
                        has_audio = True
                        is_voice = getattr(attr, "voice", False)
                    elif isinstance(attr, DocumentAttributeAnimated):
                        has_animated = True
                # Priority: sticker > audio > animated > video > file
                if has_sticker:
                    return f"стикер {sticker_emoji}".strip()
                if has_audio:
                    return "голосовое сообщение" if is_voice else "аудио"
                if has_animated:
                    return "гифка"
                if has_video:
                    return "видеосообщение" if is_round else "видео"
                return "файл"
            return "медиа"

        async def _should_respond_in_group(event, text: str) -> bool:
            if not text:
                return False
            # SAFETY: by default Sonya does NOT respond in any group. Groups are
            # for observation only — she's a userbot used as a personal AI, not
            # a chat-bot. Spam groups, dialog-mention triggers, and bot-loop
            # situations have caused identity-leak before (e.g. responding "Иван,
            # хватит" to spam in a third-party chat she was added to).
            #
            # Opt-in groups can be configured later via env. For now: hard off.
            return False
            # legacy logic kept for reference (commented out)
            # text_lower = text.lower()
            # if my_username and f"@{my_username}" in text_lower:
            #     return True
            # if my_first_name and text_lower.startswith(my_first_name):
            #     return True
            # if event.reply_to_msg_id:
            #     try:
            #         replied = await event.get_reply_message()
            #         if replied and replied.sender_id == my_id:
            #             return True
            #     except Exception:
            #         pass
            # return False

        @client.on(events.NewMessage(incoming=True))
        async def _handler(event):
            try:
                # Skip everything for groups by default — Sonya is a userbot,
                # she's just present there for observation, not interaction.
                # Don't even mark as read or download media — that costs network,
                # disk, and continuity-stream noise.
                if not event.is_private:
                    return

                await event.mark_read()
                text = event.text or ""
                media_kind = _detect_media_kind(event)
                if not text and media_kind:
                    text = f"[{media_kind}]"

                # Download media into media_dir (if configured) so VLM-capable
                # models can actually see images / stickers. Failure here is
                # non-fatal — the message still reaches Sonya as text.
                media_path: str | None = None
                media_mime: str | None = None
                if self._media_dir and event.media:
                    try:
                        media_path, media_mime = await _download_media(
                            event, self._media_dir
                        )
                    except Exception as err:
                        _log.warning(
                            "tg_media_download_failed",
                            extra={"error": str(err), "type": type(err).__name__},
                        )

                # Capture stickers into the resend collection (private only).
                if self._sticker_store is not None and event.media:
                    try:
                        _capture_sticker(event, self._sticker_store)
                    except Exception as err:
                        _log.warning(
                            "tg_sticker_capture_failed",
                            extra={"error": str(err), "type": type(err).__name__},
                        )

                msg = ChannelMessage(
                    channel=self.name,
                    chat_id=str(event.chat_id),
                    sender_id=str(event.sender_id),
                    text=text,
                    is_private=event.is_private,
                    media_kind=media_kind,
                    media_path=media_path,
                    media_mime=media_mime,
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
                        "media_path": msg.media_path,
                        "media_mime": msg.media_mime,
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
                    # Skip typing indicator if client just disconnected (race
                    # with shutdown / network blip). The reply itself will
                    # still be attempted below — Telethon retries connect on
                    # send_message.
                    try:
                        async with client.action(event.chat_id, "typing"):
                            response = await deps.on_incoming(msg)
                    except (ConnectionError, OSError, RPCError):
                        response = await deps.on_incoming(msg)
                    if response and response.text:
                        now = time.time()
                        last = last_msg_time.get(event.chat_id, 0)
                        try:
                            # Extract [STICKER: <emoji>] markers; remaining
                            # text is sent normally, then one sticker per emoji.
                            clean_text, sticker_emojis = extract_sticker_markers(response.text)
                            if clean_text:
                                chunks = _split_for_telegram(clean_text)
                                for i, chunk in enumerate(chunks):
                                    use_reply = (
                                        i == 0
                                        and (not event.is_private or now - last > 120)
                                    )
                                    if use_reply:
                                        await event.reply(chunk)
                                    else:
                                        await event.respond(chunk)
                            # Send each sticker on a separate message; the
                            # store is searched by emoji and the first match
                            # wins (most recently seen / most popular).
                            if self._sticker_store is not None:
                                for emoji in sticker_emojis:
                                    await send_sticker_by_emoji(
                                        client, event.chat_id, emoji, self._sticker_store,
                                    )
                            last_msg_time[event.chat_id] = now
                        except (ConnectionError, OSError, RPCError) as conn_err:
                            _log.warning(
                                "tg_send_skipped_disconnected",
                                extra={"chat_id": str(event.chat_id), "error": str(conn_err)},
                            )
                # NB: when should_respond=False we deliberately DO NOT call
                # deps.on_incoming. Earlier code did so "for tracking" but
                # on_incoming runs the full LLM planner — which means anyone
                # DMing Sonya from outside the allowlist could burn tokens
                # without ever receiving a reply (the response was discarded
                # here anyway). That's a budget-DoS vector. Tracking already
                # happened via deps.notify_external_event() above.
            except (ConnectionError, OSError, RPCError) as err:
                _log.warning(
                    "tg_handler_disconnected",
                    extra={"error": str(err)},
                )
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
        """Outbound message — used by initiative path or admin commands.

        v20 (Atrium Этап 0): channel-filter. Telegram bridge is a renderer
        for the `dialog` channel only. Messages from worker_log / mind /
        body / voice channels are silently dropped here — they render in
        Atrium pane'ах через /atrium/feed, not in TG. См. docs/atrium/
        CHANNELS.md §6.

        This replaces the throttle-based suppression of worker spam — the
        architectural fix instead of patching dedup/quiet-window endlessly.
        """
        # Channel filter: only dialog goes to TG.
        msg_channel = getattr(message, "channel", "dialog") or "dialog"
        if msg_channel != "dialog":
            _log.debug(
                "tg_skip_channel",
                extra={"channel": msg_channel, "preview": (message.text or "")[:80]},
            )
            return  # silently drop, не считаем в outbound metrics
        if not self._running or self._client is None:
            raise RuntimeError("telegram channel not running")
        try:
            tg_chat_id = int(chat_id)
        except ValueError as err:
            raise ValueError(f"telegram chat_id must be int-compatible, got: {chat_id}") from err

        # Retry/backoff on FloodWaitError. Telegram throttles bursts;
        # without retry, the message is just lost (audit 31.05 #16).
        # On FloodWait we wait for the requested seconds (capped to 5min)
        # and try once more. On other transient errors we retry with
        # exponential backoff.
        from telethon.errors import FloodWaitError, RPCError, ServerError

        async def _send_once() -> None:
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

        max_attempts = 3
        last_err: Exception | None = None
        for attempt in range(max_attempts):
            try:
                await _send_once()
                self._last_msg_time[tg_chat_id] = time.time()
                return
            except FloodWaitError as err:
                wait_s = min(int(getattr(err, "seconds", 30)), 300)
                _log.warning(
                    "tg_flood_wait",
                    chat_id=tg_chat_id, wait_seconds=wait_s, attempt=attempt,
                )
                if attempt + 1 < max_attempts:
                    import asyncio as _asyncio
                    await _asyncio.sleep(wait_s)
                last_err = err
            except (RPCError, ServerError, ConnectionError, OSError) as err:
                # Transient network / Telegram backend error — backoff
                # and retry. Permanent errors (chat not found, no perms)
                # are RPCError subclasses too, so cap attempts.
                _log.warning(
                    "tg_send_transient_error",
                    chat_id=tg_chat_id, error=str(err)[:200], attempt=attempt,
                )
                if attempt + 1 < max_attempts:
                    import asyncio as _asyncio
                    await _asyncio.sleep(2.0 * (2 ** attempt))
                last_err = err
        # Exhausted retries
        if last_err is not None:
            raise last_err
        raise RuntimeError("tg send failed without explicit error")


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

    # Sticker store needs substrate. The composition root passes substrate
    # through ChannelDeps.substrate but build() runs before deps are wired.
    # We accept that the build() factory can't construct it here and leave
    # it None — main._on_incoming/composition layer wires it after start().
    return TelegramChannel(
        api_id=api_id,
        api_hash=getattr(config, "tg_api_hash", ""),
        session_path=getattr(config, "tg_session_path", "./tg.session"),
        allowed_sender_ids=allowed,
        media_dir=str(getattr(config, "media_dir", "")) or None,
        sticker_store=None,
    )


async def _download_media(event: Any, media_dir: str) -> tuple[str | None, str | None]:
    """Download a Telegram message's media into media_dir.

    Returns (absolute_path, mime_type) on success, (None, None) on no-op.
    Skips audio/voice for now (they need different handling for transcription).

    Filename: <msg_id>_<chat_id>.<ext>. Stable so re-downloads overwrite cleanly.
    """
    from pathlib import Path
    from telethon.tl.types import (
        DocumentAttributeAudio,
        DocumentAttributeAnimated,
        DocumentAttributeSticker,
        DocumentAttributeVideo,
        MessageMediaDocument,
        MessageMediaPhoto,
    )

    media = event.media
    if media is None:
        return None, None

    # Decide extension + skip set
    ext = "bin"
    mime = None
    if isinstance(media, MessageMediaPhoto):
        ext = "jpg"
        mime = "image/jpeg"
    elif isinstance(media, MessageMediaDocument) and media.document:
        doc = media.document
        mime = doc.mime_type or ""
        attrs = doc.attributes or []
        is_voice = False
        is_sticker = False
        is_video = False
        for attr in attrs:
            if isinstance(attr, DocumentAttributeAudio) and getattr(attr, "voice", False):
                is_voice = True
            if isinstance(attr, DocumentAttributeSticker):
                is_sticker = True
            elif isinstance(attr, DocumentAttributeAnimated):
                pass  # handled below
            elif isinstance(attr, DocumentAttributeVideo):
                is_video = True
        if is_voice:
            return None, None
        if is_sticker:
            if mime == "application/x-tgsticker":
                # .tgs (Lottie vector animation) — can't send to VLM
                return None, None
            if is_video:
                # Video sticker — short WebM loop. Send as video.
                ext = "webm"
                mime = "video/webm"
            else:
                # Static sticker — webp image
                ext = "webp"
                mime = "image/webp"
        elif is_video:
            ext = "mp4"
            # Telethon sometimes reports mime as empty or wrong for video
            if not mime or mime == "image/webp":
                mime = "video/mp4"
        else:
            # Check for animated GIF-like docs
            for attr in attrs:
                if isinstance(attr, DocumentAttributeAnimated):
                    ext = "mp4"
                    break
        # Fallback: derive from mime
        if ext == "bin" and mime:
            mime_to_ext = {
                "image/jpeg": "jpg",
                "image/png": "png",
                "image/webp": "webp",
                "image/gif": "gif",
                "video/mp4": "mp4",
            }
            ext = mime_to_ext.get(mime, "bin")
    else:
        return None, None

    out_path = Path(media_dir) / f"{event.id}_{event.chat_id}.{ext}"
    # Telethon's download_media accepts a path string or file object
    saved = await event.download_media(file=str(out_path))
    if saved is None:
        return None, None
    return str(saved), mime


# Telegram's text limit is 4096 chars per message. We leave a small margin for
# safety (some entities expand server-side).
_TG_HARD_LIMIT = 4000


def _split_for_telegram(text: str) -> list[str]:
    """Split a long reply into Telegram-safe chunks at natural boundaries.

    Strategy:
      1. If <= limit — return as-is.
      2. Try to split on paragraph breaks (\\n\\n).
      3. Fall back to sentence boundaries (. ! ?).
      4. Last resort — hard char split.
    Empty input returns [].
    """
    if not text:
        return []
    if len(text) <= _TG_HARD_LIMIT:
        return [text]

    out: list[str] = []
    remainder = text
    while remainder:
        if len(remainder) <= _TG_HARD_LIMIT:
            out.append(remainder)
            break
        window = remainder[:_TG_HARD_LIMIT]
        # Prefer paragraph break
        cut = window.rfind("\n\n")
        if cut < _TG_HARD_LIMIT // 2:
            cut = -1  # too early, look for sentence boundary instead
        if cut < 0:
            # Sentence boundary: last . ! ? followed by whitespace
            for sep in (". ", "! ", "? ", ".\n", "!\n", "?\n"):
                idx = window.rfind(sep)
                if idx > _TG_HARD_LIMIT // 2:
                    cut = idx + len(sep) - 1
                    break
        if cut < 0:
            # Whitespace
            cut = window.rfind(" ")
        if cut <= 0:
            # Hard split — no good boundary
            cut = _TG_HARD_LIMIT
        out.append(remainder[:cut].rstrip())
        remainder = remainder[cut:].lstrip()
    return out


# ====================================================================
# Sticker capture + send helpers
# ====================================================================

import re as _re_stickers

# Marker Sonya emits in her reply when she wants to send a sticker:
#   [STICKER: 😘]
# Single emoji per marker. Multiple markers in one reply are allowed.
_STICKER_MARKER_RE = _re_stickers.compile(r"\[STICKER:\s*([^\]]+)\]")


def _capture_sticker(event: Any, sticker_store: Any) -> None:
    """If the message contains a sticker document, persist it for re-send.

    Telegram stickers are MessageMediaDocument with a DocumentAttributeSticker
    inside attributes. We extract file_id, access_hash, file_reference,
    emoji (alt), and the pack short_name.
    """
    from telethon.tl.types import (
        DocumentAttributeSticker,
        InputStickerSetID,
        InputStickerSetShortName,
        MessageMediaDocument,
    )

    media = event.media
    if not isinstance(media, MessageMediaDocument):
        return
    doc = media.document
    if doc is None:
        return

    sticker_attr = None
    for attr in (doc.attributes or []):
        if isinstance(attr, DocumentAttributeSticker):
            sticker_attr = attr
            break
    if sticker_attr is None:
        return  # not a sticker — could be voice, video, animated, etc.

    # alt is a single emoji (or empty string for some custom packs)
    emoji = (sticker_attr.alt or "").strip()
    pack_name = ""
    stickerset = sticker_attr.stickerset
    if isinstance(stickerset, InputStickerSetShortName):
        pack_name = stickerset.short_name or ""
    elif isinstance(stickerset, InputStickerSetID):
        pack_name = f"id:{stickerset.id}"

    sticker_store.upsert(
        file_id=int(doc.id),
        access_hash=int(doc.access_hash),
        file_reference=bytes(doc.file_reference) if doc.file_reference else b"",
        emoji=emoji,
        pack_name=pack_name,
        mime_type=doc.mime_type or "",
    )


def extract_sticker_markers(text: str) -> tuple[str, list[str]]:
    """Split a reply into (clean_text, [emoji, emoji, ...]).

    `[STICKER: 😘]` markers are stripped from the text and their emojis
    returned in order. Caller is expected to send the cleaned text first
    and then one sticker per emoji.
    """
    if not text:
        return "", []
    emojis = [m.group(1).strip() for m in _STICKER_MARKER_RE.finditer(text)]
    cleaned = _STICKER_MARKER_RE.sub("", text)
    # Collapse triple+ newlines that resulted from removed lines
    cleaned = _re_stickers.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned, emojis


async def send_sticker_by_emoji(
    client: Any,
    chat_id: Any,
    emoji: str,
    sticker_store: Any,
) -> bool:
    """Pick a remembered sticker matching this emoji and send it.

    Returns True on success, False if no sticker is known or the send
    failed. Increments use_count on success.
    """
    from telethon.tl.types import InputDocument

    sticker = sticker_store.pick_for_emoji(emoji)
    if sticker is None:
        return False
    try:
        input_doc = InputDocument(
            id=sticker.file_id,
            access_hash=sticker.access_hash,
            file_reference=sticker.file_reference,
        )
        await client.send_file(chat_id, input_doc)
        sticker_store.mark_used(sticker.sticker_id)
        return True
    except Exception as err:
        _log.warning(
            "tg_sticker_send_failed",
            extra={
                "error": str(err),
                "type": type(err).__name__,
                "emoji": emoji,
                "sticker_id": sticker.sticker_id,
            },
        )
        return False
