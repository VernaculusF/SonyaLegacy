from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from sonya_runtime.actions.models import RuntimeTaskPayload
from sonya_runtime.tasks.models import TaskRecord, utc_now_iso


class SQLiteTaskStore:
    def __init__(self, db_path: Path | str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def close(self) -> None:
        self.conn.close()

    def _init_schema(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                goal TEXT NOT NULL,
                context_summary TEXT NOT NULL DEFAULT '',
                source_message TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL,
                priority INTEGER NOT NULL DEFAULT 3,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                requested_by_principal TEXT NOT NULL DEFAULT '',
                origin_channel TEXT NOT NULL DEFAULT '',
                origin_chat_id TEXT NOT NULL DEFAULT '',
                result_summary TEXT NOT NULL DEFAULT '',
                result_payload TEXT NOT NULL DEFAULT '{}',
                error_text TEXT NOT NULL DEFAULT '',
                claimed_actions TEXT NOT NULL DEFAULT '[]',
                followup_required INTEGER NOT NULL DEFAULT 0,
                followup_prompt TEXT NOT NULL DEFAULT '',
                worker_id TEXT NOT NULL DEFAULT '',
                suggested_steps TEXT NOT NULL DEFAULT '[]'
            );
            CREATE INDEX IF NOT EXISTS idx_tasks_status_priority_created
            ON tasks(status, priority DESC, created_at ASC);
            CREATE INDEX IF NOT EXISTS idx_tasks_principal_status
            ON tasks(requested_by_principal, status, updated_at DESC);
            """
        )
        self.conn.commit()

    def _row_to_record(self, row: sqlite3.Row | None) -> TaskRecord | None:
        if row is None:
            return None
        return TaskRecord(
            task_id=row["task_id"],
            kind=row["kind"],
            goal=row["goal"],
            context_summary=row["context_summary"],
            source_message=row["source_message"],
            status=row["status"],
            priority=int(row["priority"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            requested_by_principal=row["requested_by_principal"],
            origin_channel=row["origin_channel"],
            origin_chat_id=row["origin_chat_id"],
            result_summary=row["result_summary"],
            result_payload=json.loads(row["result_payload"] or "{}"),
            error_text=row["error_text"],
            claimed_actions=tuple(json.loads(row["claimed_actions"] or "[]")),
            followup_required=bool(row["followup_required"]),
            followup_prompt=row["followup_prompt"],
            worker_id=row["worker_id"],
            suggested_steps=tuple(json.loads(row["suggested_steps"] or "[]")),
        )

    def create_task(self, payload: RuntimeTaskPayload) -> TaskRecord:
        from sonya_shared.ids import new_task_id

        now = utc_now_iso()
        task_id = new_task_id()
        self.conn.execute(
            """
            INSERT INTO tasks (
                task_id, kind, goal, context_summary, source_message, status, priority,
                created_at, updated_at, requested_by_principal, origin_channel, origin_chat_id,
                followup_required, followup_prompt, suggested_steps
            ) VALUES (?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task_id,
                payload.kind,
                payload.goal,
                payload.context_summary,
                payload.source_message,
                payload.priority,
                now,
                now,
                payload.requested_by_principal,
                payload.origin_channel,
                payload.origin_chat_id,
                1 if payload.requires_user_followup else 0,
                payload.followup_prompt,
                json.dumps(list(payload.suggested_steps), ensure_ascii=False),
            ),
        )
        self.conn.commit()
        return self.get_task(task_id)  # type: ignore[return-value]

    def get_task(self, task_id: str) -> TaskRecord | None:
        row = self.conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        return self._row_to_record(row)

    def list_tasks(self, status: str | None = None, limit: int = 50) -> list[TaskRecord]:
        if status:
            rows = self.conn.execute(
                "SELECT * FROM tasks WHERE status = ? ORDER BY priority DESC, created_at ASC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM tasks ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [record for row in rows if (record := self._row_to_record(row)) is not None]

    def claim_next_task(self, worker_id: str, allowed_kinds: set[str] | None = None) -> TaskRecord | None:
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            params: list[object] = []
            query = "SELECT task_id FROM tasks WHERE status = 'pending'"
            if allowed_kinds:
                placeholders = ",".join("?" for _ in allowed_kinds)
                query += f" AND kind IN ({placeholders})"
                params.extend(sorted(allowed_kinds))
            query += " ORDER BY priority DESC, created_at ASC LIMIT 1"
            row = self.conn.execute(query, params).fetchone()
            if row is None:
                self.conn.rollback()
                return None
            task_id = row["task_id"]
            now = utc_now_iso()
            updated = self.conn.execute(
                """
                UPDATE tasks
                SET status = 'running', worker_id = ?, updated_at = ?
                WHERE task_id = ? AND status = 'pending'
                """,
                (worker_id, now, task_id),
            )
            if updated.rowcount != 1:
                self.conn.rollback()
                return None
            self.conn.commit()
            return self.get_task(task_id)
        except Exception:
            self.conn.rollback()
            raise

    def mark_running(self, task_id: str, worker_id: str) -> TaskRecord | None:
        now = utc_now_iso()
        updated = self.conn.execute(
            "UPDATE tasks SET status = 'running', worker_id = ?, updated_at = ? WHERE task_id = ?",
            (worker_id, now, task_id),
        )
        self.conn.commit()
        return self.get_task(task_id) if updated.rowcount else None

    def mark_done(self, task_id: str, result_summary: str, result_payload: dict | None = None) -> TaskRecord | None:
        now = utc_now_iso()
        updated = self.conn.execute(
            """
            UPDATE tasks
            SET status = 'done', result_summary = ?, result_payload = ?, error_text = '', updated_at = ?
            WHERE task_id = ?
            """,
            (result_summary, json.dumps(result_payload or {}, ensure_ascii=False), now, task_id),
        )
        self.conn.commit()
        return self.get_task(task_id) if updated.rowcount else None

    def mark_failed(self, task_id: str, error_text: str) -> TaskRecord | None:
        now = utc_now_iso()
        updated = self.conn.execute(
            "UPDATE tasks SET status = 'failed', error_text = ?, updated_at = ? WHERE task_id = ?",
            (error_text, now, task_id),
        )
        self.conn.commit()
        return self.get_task(task_id) if updated.rowcount else None

    def cancel_task(self, task_id: str) -> TaskRecord | None:
        now = utc_now_iso()
        updated = self.conn.execute(
            "UPDATE tasks SET status = 'cancelled', updated_at = ? WHERE task_id = ?",
            (now, task_id),
        )
        self.conn.commit()
        return self.get_task(task_id) if updated.rowcount else None

    def get_open_tasks_for_principal(self, principal_id: str, origin_chat_id: str | None = None) -> list[TaskRecord]:
        params: list[object] = [principal_id]
        query = """
            SELECT * FROM tasks
            WHERE requested_by_principal = ?
              AND status IN ('pending', 'running')
        """
        if origin_chat_id:
            query += " AND origin_chat_id = ?"
            params.append(origin_chat_id)
        query += " ORDER BY priority DESC, updated_at DESC"
        rows = self.conn.execute(query, params).fetchall()
        return [record for row in rows if (record := self._row_to_record(row)) is not None]

    def get_recent_tasks_for_principal(self, principal_id: str, origin_chat_id: str | None = None, limit: int = 5) -> list[TaskRecord]:
        params: list[object] = [principal_id]
        query = "SELECT * FROM tasks WHERE requested_by_principal = ?"
        if origin_chat_id:
            query += " AND origin_chat_id = ?"
            params.append(origin_chat_id)
        query += " ORDER BY updated_at DESC LIMIT ?"
        params.append(limit)
        rows = self.conn.execute(query, params).fetchall()
        return [record for row in rows if (record := self._row_to_record(row)) is not None]
