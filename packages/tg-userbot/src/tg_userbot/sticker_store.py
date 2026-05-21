"""Sticker collection — what Sonya has seen, what she can re-send.

Substrate-backed registry of stickers received from Ivan. Each row is a
single sticker document (Telegram InputDocument key = file_id+access_hash).
When Sonya wants to send a sticker, she emits `[STICKER: <emoji>]` in her
reply; we look up the most-used or most-recent sticker matching that emoji
and re-send it through Telethon.

Substrate v14 table: seen_stickers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sonya.state.substrate import Substrate


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class SeenSticker:
    sticker_id: str
    file_id: int
    access_hash: int
    file_reference: bytes
    emoji: str
    pack_name: str
    mime_type: str
    first_seen_at: str
    last_seen_at: str
    seen_count: int
    use_count: int


class StickerStore:
    """CRUD over seen_stickers."""

    def __init__(self, substrate: Substrate) -> None:
        self._sub = substrate

    @staticmethod
    def make_id(file_id: int, access_hash: int) -> str:
        return f"{file_id}:{access_hash}"

    def upsert(
        self,
        *,
        file_id: int,
        access_hash: int,
        file_reference: bytes,
        emoji: str,
        pack_name: str,
        mime_type: str,
    ) -> None:
        """Record an incoming sticker. Increments seen_count if already known."""
        sticker_id = self.make_id(file_id, access_hash)
        now = _utc_now_iso()
        row = self._sub.connection.execute(
            "SELECT seen_count FROM seen_stickers WHERE sticker_id = ?",
            (sticker_id,),
        ).fetchone()
        if row is None:
            self._sub.connection.execute(
                "INSERT INTO seen_stickers"
                "(sticker_id, file_id, access_hash, file_reference, emoji, "
                "pack_name, mime_type, first_seen_at, last_seen_at, "
                "seen_count, use_count) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0)",
                (sticker_id, file_id, access_hash, file_reference,
                 emoji, pack_name, mime_type, now, now),
            )
        else:
            # Refresh file_reference (it expires) and bump seen_count.
            self._sub.connection.execute(
                "UPDATE seen_stickers SET seen_count = seen_count + 1, "
                "last_seen_at = ?, file_reference = ? WHERE sticker_id = ?",
                (now, file_reference, sticker_id),
            )
        self._sub.connection.commit()

    def find_by_emoji(self, emoji: str, limit: int = 5) -> list[SeenSticker]:
        """Return up-to N stickers matching this emoji, prioritising last-seen
        recency then seen_count (popular packs surface first)."""
        cursor = self._sub.connection.execute(
            "SELECT sticker_id, file_id, access_hash, file_reference, emoji, "
            "pack_name, mime_type, first_seen_at, last_seen_at, seen_count, use_count "
            "FROM seen_stickers WHERE emoji = ? "
            "ORDER BY last_seen_at DESC, seen_count DESC LIMIT ?",
            (emoji, limit),
        )
        return [_row_to_sticker(r) for r in cursor.fetchall()]

    def pick_for_emoji(self, emoji: str) -> Optional[SeenSticker]:
        """Pick one sticker for the given emoji. Strategy: most recently seen
        in the same pack as the most-used sticker for this emoji. Simple
        version: take the top hit."""
        results = self.find_by_emoji(emoji, limit=1)
        return results[0] if results else None

    def mark_used(self, sticker_id: str) -> None:
        self._sub.connection.execute(
            "UPDATE seen_stickers SET use_count = use_count + 1 WHERE sticker_id = ?",
            (sticker_id,),
        )
        self._sub.connection.commit()

    def count(self) -> int:
        row = self._sub.connection.execute(
            "SELECT COUNT(*) FROM seen_stickers"
        ).fetchone()
        return int(row[0])

    def list_emojis(self) -> list[tuple[str, int]]:
        """Return [(emoji, count_of_stickers), ...] sorted by count desc."""
        cursor = self._sub.connection.execute(
            "SELECT emoji, COUNT(*) FROM seen_stickers WHERE emoji != '' "
            "GROUP BY emoji ORDER BY COUNT(*) DESC"
        )
        return [(r[0], int(r[1])) for r in cursor.fetchall()]


def _row_to_sticker(row) -> SeenSticker:
    return SeenSticker(
        sticker_id=row[0],
        file_id=int(row[1]),
        access_hash=int(row[2]),
        file_reference=bytes(row[3]) if row[3] is not None else b"",
        emoji=row[4] or "",
        pack_name=row[5] or "",
        mime_type=row[6] or "",
        first_seen_at=row[7] or "",
        last_seen_at=row[8] or "",
        seen_count=int(row[9]),
        use_count=int(row[10]),
    )
