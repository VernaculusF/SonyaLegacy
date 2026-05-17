"""Import Telegram chat history (Telegram Desktop result.json) into episodic memory.

One-time migration: reads the JSON export, transforms each message into an
EpisodicEvent, and records into the live substrate.

This is how Sonya "wakes up in a new body" — same memories, new account.
The previous account (Абоба) was banned; this is the same subject continuing
in the new tg.session, with all conversation history preserved.

Usage:
    python -m sonya.tools.import_history /path/to/result.json
    python -m sonya.tools.import_history /path/to/result.json --dry-run
    python -m sonya.tools.import_history /path/to/result.json --limit 100

Idempotency: each message gets a deterministic event_id derived from the
source message id. Re-running the import skips messages already present.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sonya.config import load_config
from sonya.state.substrate import Substrate


def _flatten_text(text_field: Any) -> str:
    """Telegram Desktop stores text as either str or list of mixed dict/str chunks."""
    if isinstance(text_field, str):
        return text_field
    if isinstance(text_field, list):
        parts: list[str] = []
        for chunk in text_field:
            if isinstance(chunk, str):
                parts.append(chunk)
            elif isinstance(chunk, dict):
                parts.append(str(chunk.get("text", "")))
        return "".join(parts)
    return ""


def _normalize_actor(message: dict[str, Any]) -> str:
    """Map sender to 'ivan' or 'sonya' for downstream context."""
    from_field = (message.get("from") or "").lower()
    from_id = message.get("from_id", "")
    if "иван" in from_field or "ivan" in from_field or "jester" in from_field:
        return "ivan"
    # Bot/Sonya — typically the other side of a 1:1 chat
    if from_id.startswith("user") and "5785127604" not in from_id:
        return "sonya"
    return from_field or "unknown"


def _to_iso(date_str: str) -> str:
    """Normalize TG Desktop date to UTC ISO."""
    try:
        dt = datetime.fromisoformat(date_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return date_str


def import_messages(
    substrate: Substrate,
    json_path: Path,
    *,
    dry_run: bool = False,
    limit: int | None = None,
    chat_label: str = "telegram_legacy",
) -> dict[str, int]:
    """Import all text messages from the JSON export.

    Skips empty/system messages. Generates deterministic event_ids so re-runs
    are idempotent.
    """
    data = json.loads(json_path.read_text(encoding="utf-8"))
    raw_messages: list[dict[str, Any]] = data.get("messages", [])

    if limit is not None:
        raw_messages = raw_messages[:limit]

    chat_name = data.get("name", "unknown")
    chat_id = data.get("id", 0)

    stats = {"total": 0, "imported": 0, "skipped_empty": 0, "skipped_existing": 0, "skipped_system": 0}

    # Build set of already-existing event_ids to avoid duplicate inserts
    existing_ids: set[str] = set()
    if not dry_run:
        cursor = substrate.connection.execute(
            "SELECT event_id FROM episodic_events WHERE event_id LIKE 'tg-import-%'"
        )
        existing_ids = {row[0] for row in cursor.fetchall()}

    for msg in raw_messages:
        stats["total"] += 1

        if msg.get("type") != "message":
            stats["skipped_system"] += 1
            continue

        text = _flatten_text(msg.get("text") or "")
        if not text.strip():
            # Could be media-only — skip for now (history import is text-focused)
            stats["skipped_empty"] += 1
            continue

        msg_id = msg.get("id")
        event_id = f"tg-import-{chat_id}-{msg_id}"
        if event_id in existing_ids:
            stats["skipped_existing"] += 1
            continue

        actor = _normalize_actor(msg)
        timestamp = _to_iso(msg.get("date", ""))

        # Importance heuristic: short reactions get 0.4, normal exchanges 0.55,
        # longer / emotionally-loaded 0.65. We can't actually score from text length
        # alone, but mid-tier seems sensible.
        text_len = len(text)
        if text_len < 30:
            importance = 0.4
        elif text_len < 200:
            importance = 0.55
        else:
            importance = 0.65

        normalized_summary = (
            f"{actor}: {text[:120]}" + ("..." if len(text) > 120 else "")
        )

        if dry_run:
            stats["imported"] += 1
            continue

        # Direct INSERT to bypass uuid generation in EpisodicMemory.record()
        # (we want deterministic event_id for idempotency)
        substrate.connection.execute(
            "INSERT INTO episodic_events"
            "(event_id, event_type, timestamp, source, channel, actor, "
            "raw_content, normalized_summary, emotion_tags_json, "
            "importance_score, retention_strength, last_accessed_at, access_count, archived) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1.0, ?, 0, 0)",
            (
                event_id,
                "dialogue_event",
                timestamp,
                "tg_history_import",
                chat_label,
                actor,
                text[:5000],
                normalized_summary,
                "[]",
                importance,
                timestamp,
            ),
        )
        stats["imported"] += 1

    if not dry_run:
        substrate.connection.commit()

    return stats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import TG chat history into Sonya substrate")
    parser.add_argument("json_path", type=Path, help="Path to result.json from TG Desktop export")
    parser.add_argument("--dry-run", action="store_true", help="Don't write to substrate, just count")
    parser.add_argument("--limit", type=int, default=None, help="Import only first N messages")
    parser.add_argument("--label", type=str, default="telegram_legacy", help="channel label for events")
    args = parser.parse_args(argv)

    if not args.json_path.exists():
        print(f"File not found: {args.json_path}", file=sys.stderr)
        return 2

    config = load_config()
    sub = Substrate.open(config.substrate_path)
    try:
        stats = import_messages(
            sub,
            args.json_path,
            dry_run=args.dry_run,
            limit=args.limit,
            chat_label=args.label,
        )
        prefix = "DRY RUN: " if args.dry_run else ""
        print(f"{prefix}imported={stats['imported']} "
              f"skipped_empty={stats['skipped_empty']} "
              f"skipped_existing={stats['skipped_existing']} "
              f"skipped_system={stats['skipped_system']} "
              f"total={stats['total']}")
        return 0
    finally:
        sub.close()


if __name__ == "__main__":
    sys.exit(main())
