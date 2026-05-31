"""Recurring task scheduler — переоткрывает завершённые DONE/FAILED задачи
с recurring_spec в новый PENDING ряд по cadence.

`recurring_spec` — JSON в `tasks.recurring_spec`. Поддерживаемые формы:

  {"every": "1h"}              — раз в час после completed_at
  {"every": "30m"}             — раз в полчаса
  {"every": "1d"}              — раз в сутки
  {"every": "1w"}              — раз в неделю
  {"every": "1d", "at": "09:00"} — каждый день в 09:00 UTC
  {"cron": "0 9 * * *"}        — cron-style (нет пока, на будущее)

Логика:
  1. Найти все tasks где status in (DONE, FAILED) и recurring_spec != ""
     и (нет ребёнка с parent_task_id=task_id ещё в open) и (next_run <= now).
  2. Создать новый task с status=PENDING, тем же title/description/plan,
     parent_task_id ссылкой на оригинал, scheduled_for=now+grace.
  3. На рестарте идемпотентно — `_already_has_pending_recurrence` checks.

Не пересоздаём бесконечные клоны: если последний клон ещё в open
(pending/in_progress/blocked/paused) — пропускаем тик. Recurrence ждёт
пока текущий не закроется.

См. audit 31.05 #4.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sonya.tasks.models import Task, TaskStatus
from sonya.tasks.store import TaskStore


_DURATION_RE = re.compile(r"^(\d+)\s*([smhdw])$", re.IGNORECASE)
_UNIT_SECONDS = {
    "s": 1,
    "m": 60,
    "h": 3600,
    "d": 86400,
    "w": 7 * 86400,
}


def parse_duration(spec: str) -> timedelta | None:
    """Parse '30m' / '1h' / '2d' / '1w' → timedelta. Returns None on failure."""
    m = _DURATION_RE.match((spec or "").strip())
    if m is None:
        return None
    num = int(m.group(1))
    unit = m.group(2).lower()
    seconds = num * _UNIT_SECONDS.get(unit, 0)
    if seconds <= 0:
        return None
    return timedelta(seconds=seconds)


@dataclass(frozen=True, slots=True)
class RecurrenceCheck:
    """Result of evaluating a single recurring task at this moment."""

    should_clone: bool
    reason: str
    next_run_at: str = ""


def evaluate_recurrence(task: Task, *, now: datetime | None = None) -> RecurrenceCheck:
    """Decide whether this task warrants creating a fresh PENDING clone now.

    Returns RecurrenceCheck with `should_clone=True` and `reason` if so.
    """
    spec_raw = (task.recurring_spec or "").strip()
    if not spec_raw:
        return RecurrenceCheck(False, "no_spec")
    if task.status not in (TaskStatus.DONE, TaskStatus.FAILED):
        return RecurrenceCheck(False, "not_terminal")

    try:
        spec = json.loads(spec_raw)
    except (json.JSONDecodeError, TypeError):
        return RecurrenceCheck(False, "bad_spec_json")
    if not isinstance(spec, dict):
        return RecurrenceCheck(False, "bad_spec_shape")

    every = str(spec.get("every", "")).strip()
    if not every:
        return RecurrenceCheck(False, "no_every_field")
    delta = parse_duration(every)
    if delta is None:
        return RecurrenceCheck(False, f"bad_every_value:{every}")

    if now is None:
        now = datetime.now(timezone.utc)

    # `updated_at` of a DONE/FAILED row is when status was set terminal.
    # That's the reference for next_run = updated_at + delta.
    try:
        updated = datetime.fromisoformat(task.updated_at.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return RecurrenceCheck(False, "unparseable_updated_at")
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=timezone.utc)

    next_run = updated + delta

    # Optional `at` field — pin to specific UTC time-of-day.
    at_str = str(spec.get("at", "")).strip()
    if at_str:
        try:
            hh, mm = at_str.split(":", 1)
            target_hour, target_minute = int(hh), int(mm)
            # Roll forward to the next occurrence of HH:MM at-or-after next_run
            candidate = next_run.replace(
                hour=target_hour, minute=target_minute, second=0, microsecond=0,
            )
            if candidate < next_run:
                candidate += timedelta(days=1)
            next_run = candidate
        except (ValueError, IndexError):
            pass

    if now < next_run:
        return RecurrenceCheck(False, "not_due_yet", next_run_at=next_run.isoformat())

    return RecurrenceCheck(True, "due", next_run_at=next_run.isoformat())


class RecurrenceScheduler:
    """Watcher invoked from internal_loop tick — at most once / 5min."""

    def __init__(self, store: TaskStore) -> None:
        self._store = store

    def _has_open_clone(self, parent_id: str) -> bool:
        """Are there any open (pending/in_progress/blocked/paused) descendants
        of `parent_id` already? If yes, don't spawn another."""
        cursor = self._store._sub.connection.execute(
            "SELECT task_id FROM tasks WHERE parent_task_id = ? "
            "AND status IN ('pending', 'in_progress', 'blocked', 'paused')",
            (parent_id,),
        )
        return cursor.fetchone() is not None

    def run_once(self) -> list[dict[str, Any]]:
        """Scan all tasks with recurring_spec, clone where due. Returns
        list of {parent_id, new_task_id, reason} for audit/logging."""
        results: list[dict[str, Any]] = []
        # Only DONE/FAILED tasks can spawn recurrences. Pull them from store
        # directly so we don't materialise ALL tasks; recurring_spec column
        # is non-empty for the few we care about.
        rows = self._store._sub.connection.execute(
            "SELECT task_id FROM tasks "
            "WHERE recurring_spec != '' "
            "AND status IN ('done', 'failed')"
        ).fetchall()
        for (tid,) in rows:
            task = self._store.get(tid)
            if task is None:
                continue
            if self._has_open_clone(task.task_id):
                continue
            check = evaluate_recurrence(task)
            if not check.should_clone:
                continue
            try:
                clone = self._store.create(
                    title=task.title,
                    description=task.description,
                    plan_steps=list(task.plan_steps),
                    principal_id=task.principal_id,
                    parent_task_id=task.task_id,
                    deadline=task.deadline,
                    created_by=task.created_by,
                    scheduled_for="",
                    recurring_spec=task.recurring_spec,
                    notify_mode=task.notify_mode,
                    max_sessions=task.max_sessions,
                    urgency=task.urgency,
                )
                results.append({
                    "parent_id": task.task_id,
                    "new_task_id": clone.task_id,
                    "reason": check.reason,
                    "next_run_at": check.next_run_at,
                })
            except Exception as exc:
                results.append({
                    "parent_id": task.task_id,
                    "new_task_id": "",
                    "reason": f"create_failed:{type(exc).__name__}",
                })
        return results


__all__ = [
    "parse_duration",
    "evaluate_recurrence",
    "RecurrenceCheck",
    "RecurrenceScheduler",
]
