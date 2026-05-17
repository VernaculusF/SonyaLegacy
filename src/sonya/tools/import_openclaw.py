"""Import OpenClaw memory_system/db/memory.db into Sonya's substrate.

Maps:
- facts        → semantic_facts (fact_type derived from category)
- events       → episodic_events (event_type='dialogue_event'/'milestone'/...)
- lessons      → semantic_facts (fact_type='lesson')
- research     → semantic_facts (fact_type='research_topic'; full_text into raw)
- goals (active) → tasks (status=pending/in_progress)
- working_memory → episodic_events (event_type='working_memory', importance lowered)
- thinking_process → episodic_events (event_type='internal_thought')

All inserts get deterministic IDs prefixed with 'openclaw-' so re-runs skip duplicates.

Usage:
    python -m sonya.tools.import_openclaw /path/to/memory.db
    python -m sonya.tools.import_openclaw /path/to/memory.db --dry-run
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sonya.config import load_config
from sonya.state.substrate import Substrate


def _utc(dt_str: str | None) -> str:
    if not dt_str:
        return datetime.now(timezone.utc).isoformat()
    s = dt_str.strip()
    # SQLite default 'YYYY-MM-DD HH:MM:SS' is naive; treat as UTC.
    try:
        if " " in s and "T" not in s:
            s = s.replace(" ", "T")
        if "+" not in s and "Z" not in s and not s.endswith(":00"):
            s = s + "+00:00"
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return datetime.now(timezone.utc).isoformat()


def _existing_ids(sub: Substrate, prefix: str, table: str, col: str) -> set[str]:
    rows = sub.connection.execute(
        f"SELECT {col} FROM {table} WHERE {col} LIKE ?",
        (f"{prefix}%",),
    ).fetchall()
    return {r[0] for r in rows}


def import_facts(src: sqlite3.Connection, sub: Substrate, *, dry_run: bool) -> int:
    rows = src.execute(
        "SELECT id, category, subject, fact, confidence, source, created_at FROM facts"
    ).fetchall()
    existing = _existing_ids(sub, "openclaw-fact-", "semantic_facts", "fact_id") if not dry_run else set()
    imported = 0
    for fid, category, subject, fact, conf, source, created in rows:
        fact_id = f"openclaw-fact-{fid}"
        if fact_id in existing:
            continue
        if dry_run:
            imported += 1
            continue
        statement = f"[{subject or 'unknown'}] {fact}" if subject else str(fact)
        ts = _utc(created)
        sub.connection.execute(
            "INSERT INTO semantic_facts(fact_id, fact_type, statement, "
            "source_event_ids_json, confidence, last_reinforced_at, contradiction_flags_json) "
            "VALUES (?, ?, ?, '[]', ?, ?, '[]')",
            (
                fact_id,
                f"openclaw_{category}" if category else "openclaw_fact",
                statement[:2000],
                float(conf or 0.7),
                ts,
            ),
        )
        imported += 1
    if not dry_run:
        sub.connection.commit()
    return imported


def import_lessons(src: sqlite3.Connection, sub: Substrate, *, dry_run: bool) -> int:
    rows = src.execute(
        "SELECT id, lesson, category, learned_from, applied_count, created_at FROM lessons"
    ).fetchall()
    existing = _existing_ids(sub, "openclaw-lesson-", "semantic_facts", "fact_id") if not dry_run else set()
    imported = 0
    for fid, lesson, category, learned_from, applied, created in rows:
        fact_id = f"openclaw-lesson-{fid}"
        if fact_id in existing:
            continue
        if dry_run:
            imported += 1
            continue
        # Lessons are first-class self-improvement rules
        statement = f"[lesson:{category or 'general'}] {lesson}"
        if learned_from:
            statement += f"\nЧтоб не забыть откуда: {learned_from[:500]}"
        ts = _utc(created)
        sub.connection.execute(
            "INSERT INTO semantic_facts(fact_id, fact_type, statement, "
            "source_event_ids_json, confidence, last_reinforced_at, contradiction_flags_json) "
            "VALUES (?, 'lesson', ?, '[]', ?, ?, '[]')",
            (fact_id, statement[:3000], 0.9, ts),
        )
        imported += 1
    if not dry_run:
        sub.connection.commit()
    return imported


def import_research(src: sqlite3.Connection, sub: Substrate, *, dry_run: bool) -> int:
    rows = src.execute(
        "SELECT id, topic, category, summary, full_text, sources, created_at FROM research"
    ).fetchall()
    existing = _existing_ids(sub, "openclaw-research-", "semantic_facts", "fact_id") if not dry_run else set()
    imported = 0
    for rid, topic, category, summary, full_text, sources, created in rows:
        fact_id = f"openclaw-research-{rid}"
        if fact_id in existing:
            continue
        if dry_run:
            imported += 1
            continue
        body = (summary or "")[:600]
        if full_text:
            body += f"\n---\nПолный текст исследования:\n{full_text[:2500]}"
        statement = f"[research:{topic}] {body}"
        sub.connection.execute(
            "INSERT INTO semantic_facts(fact_id, fact_type, statement, "
            "source_event_ids_json, confidence, last_reinforced_at, contradiction_flags_json) "
            "VALUES (?, 'research', ?, '[]', ?, ?, '[]')",
            (fact_id, statement[:4000], 0.7, _utc(created)),
        )
        imported += 1
    if not dry_run:
        sub.connection.commit()
    return imported


def import_events(src: sqlite3.Connection, sub: Substrate, *, dry_run: bool) -> int:
    rows = src.execute(
        "SELECT id, date, time, category, summary, details, importance, tags, created_at FROM events"
    ).fetchall()
    existing = _existing_ids(sub, "openclaw-event-", "episodic_events", "event_id") if not dry_run else set()
    imported = 0
    for eid, date, time_, category, summary, details, importance, tags, created in rows:
        event_id = f"openclaw-event-{eid}"
        if event_id in existing:
            continue
        if dry_run:
            imported += 1
            continue
        # Map to event_type
        category = (category or "").lower()
        if category == "conversation":
            etype = "dialogue_event"
        elif category in ("decision", "milestone"):
            etype = "decision"
        elif category == "problem":
            etype = "problem_observed"
        else:
            etype = "openclaw_event"

        timestamp = f"{date}T{time_ or '00:00:00'}+00:00"
        try:
            datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except Exception:
            timestamp = _utc(created)

        # Importance 1-5 → 0.2-0.9
        imp_score = max(0.2, min(0.95, 0.15 + (int(importance or 3) * 0.15)))

        raw = summary or ""
        if details:
            raw = f"{raw}\n\n{details}"
        normalized = (summary or raw)[:300]

        sub.connection.execute(
            "INSERT INTO episodic_events"
            "(event_id, event_type, timestamp, source, channel, actor, "
            "raw_content, normalized_summary, emotion_tags_json, "
            "importance_score, retention_strength, last_accessed_at, access_count, archived) "
            "VALUES (?, ?, ?, 'openclaw_import', 'openclaw_legacy', 'sonya', "
            "?, ?, ?, ?, 1.0, ?, 0, 0)",
            (
                event_id,
                etype,
                timestamp,
                raw[:5000],
                normalized,
                tags or "[]",
                imp_score,
                timestamp,
            ),
        )
        imported += 1
    if not dry_run:
        sub.connection.commit()
    return imported


def import_working_memory(src: sqlite3.Connection, sub: Substrate, *, dry_run: bool) -> int:
    rows = src.execute(
        "SELECT id, session_id, timestamp, type, content, importance, metadata FROM working_memory"
    ).fetchall()
    existing = _existing_ids(sub, "openclaw-wm-", "episodic_events", "event_id") if not dry_run else set()
    imported = 0
    for wid, session_id, ts, wtype, content, importance, metadata in rows:
        event_id = f"openclaw-wm-{wid}"
        if event_id in existing:
            continue
        if dry_run:
            imported += 1
            continue
        # Lower default importance — these are short-term scratchpad entries
        imp_score = max(0.15, min(0.7, 0.1 + (int(importance or 3) * 0.12)))
        normalized = f"[wm:{wtype}] {content[:200]}"
        sub.connection.execute(
            "INSERT INTO episodic_events"
            "(event_id, event_type, timestamp, source, channel, actor, "
            "raw_content, normalized_summary, emotion_tags_json, "
            "importance_score, retention_strength, last_accessed_at, access_count, archived) "
            "VALUES (?, 'working_memory', ?, 'openclaw_import', 'openclaw_legacy', 'sonya', "
            "?, ?, '[]', ?, 1.0, ?, 0, 0)",
            (
                event_id,
                _utc(ts),
                content[:3000],
                normalized,
                imp_score,
                _utc(ts),
            ),
        )
        imported += 1
    if not dry_run:
        sub.connection.commit()
    return imported


def import_thinking(src: sqlite3.Connection, sub: Substrate, *, dry_run: bool) -> int:
    # thinking_process table — schema unknown a priori; try common columns
    try:
        cols = [r[1] for r in src.execute("PRAGMA table_info(thinking_process)").fetchall()]
    except sqlite3.OperationalError:
        return 0
    if not cols:
        return 0

    select_cols = "id, " + ", ".join(c for c in cols if c != "id") + ", created_at" if "created_at" not in cols else (
        "id, " + ", ".join(c for c in cols if c != "id")
    )
    rows = src.execute(f"SELECT {', '.join(cols)} FROM thinking_process").fetchall()
    existing = _existing_ids(sub, "openclaw-think-", "episodic_events", "event_id") if not dry_run else set()
    imported = 0
    for row in rows:
        rec = dict(zip(cols, row))
        tid = rec.get("id")
        event_id = f"openclaw-think-{tid}"
        if event_id in existing:
            continue
        if dry_run:
            imported += 1
            continue
        ts = _utc(rec.get("created_at") or rec.get("timestamp"))
        # heuristic best-effort content
        content = (
            rec.get("thought")
            or rec.get("content")
            or rec.get("text")
            or json.dumps({k: v for k, v in rec.items() if k != "id"}, ensure_ascii=False)
        )
        sub.connection.execute(
            "INSERT INTO episodic_events"
            "(event_id, event_type, timestamp, source, channel, actor, "
            "raw_content, normalized_summary, emotion_tags_json, "
            "importance_score, retention_strength, last_accessed_at, access_count, archived) "
            "VALUES (?, 'internal_thought', ?, 'openclaw_import', 'openclaw_legacy', 'sonya', "
            "?, ?, '[]', 0.5, 1.0, ?, 0, 0)",
            (event_id, ts, str(content)[:3000], str(content)[:200], ts),
        )
        imported += 1
    if not dry_run:
        sub.connection.commit()
    return imported


def import_goals(src: sqlite3.Connection, sub: Substrate, *, dry_run: bool) -> int:
    rows = src.execute(
        "SELECT id, goal, deadline, status, priority, progress, created_at FROM goals "
        "WHERE status='active'"
    ).fetchall()
    # Use deterministic task_id with openclaw prefix
    existing = set()
    if not dry_run:
        existing = {
            r[0] for r in sub.connection.execute(
                "SELECT task_id FROM tasks WHERE task_id LIKE 'task-openclaw-%'"
            ).fetchall()
        }
    imported = 0
    for gid, goal, deadline, status, priority, progress, created in rows:
        task_id = f"task-openclaw-{gid}"
        if task_id in existing:
            continue
        if dry_run:
            imported += 1
            continue
        ts = _utc(created)
        # status mapping: active → pending (Sonya picks them up via tasks.pick)
        sub.connection.execute(
            "INSERT INTO tasks (task_id, title, description, status, principal_id, "
            "parent_task_id, deadline, plan_steps_json, completed_steps_json, "
            "blocker, result, created_at, updated_at) "
            "VALUES (?, ?, ?, 'pending', 'ivan', NULL, ?, '[]', '[]', '', '', ?, ?)",
            (
                task_id,
                goal[:200],
                f"[openclaw legacy goal]\nprogress: {progress or '{}'}",
                deadline,
                ts,
                ts,
            ),
        )
        imported += 1
    if not dry_run:
        sub.connection.commit()
    return imported


def run_import(sub: Substrate, src_path: Path, *, dry_run: bool = False) -> dict[str, int]:
    src = sqlite3.connect(str(src_path))
    src.row_factory = None
    try:
        return {
            "facts": import_facts(src, sub, dry_run=dry_run),
            "lessons": import_lessons(src, sub, dry_run=dry_run),
            "research": import_research(src, sub, dry_run=dry_run),
            "events": import_events(src, sub, dry_run=dry_run),
            "working_memory": import_working_memory(src, sub, dry_run=dry_run),
            "thinking": import_thinking(src, sub, dry_run=dry_run),
            "goals_as_tasks": import_goals(src, sub, dry_run=dry_run),
        }
    finally:
        src.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import OpenClaw memory.db into Sonya substrate")
    parser.add_argument("db_path", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if not args.db_path.exists():
        print(f"Not found: {args.db_path}", file=sys.stderr)
        return 2

    config = load_config()
    sub = Substrate.open(config.substrate_path)
    try:
        stats = run_import(sub, args.db_path, dry_run=args.dry_run)
        prefix = "DRY RUN: " if args.dry_run else ""
        for k, v in stats.items():
            print(f"{prefix}{k}: {v}")
        print(f"{prefix}TOTAL imported: {sum(stats.values())}")
        return 0
    finally:
        sub.close()


if __name__ == "__main__":
    sys.exit(main())
