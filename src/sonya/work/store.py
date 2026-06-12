"""WorkItemStore: persistent CRUD for WorkItem objects."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sonya.state.substrate import Substrate
from sonya.work.models import WorkItem, WorkItemNotFoundError, WorkItemStatus


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class WorkItemStore:
    """SQLite-backed CRUD for work_items."""

    def __init__(self, substrate: Substrate) -> None:
        self._sub = substrate

    def create(
        self,
        *,
        title: str,
        item_type: str = "task",
        description: str = "",
        owner_principal_id: str | None = None,
        origin: str = "self",
        parent_item_id: str | None = None,
        deadline: str | None = None,
        urgency: str = "normal",
        max_sessions: int = 0,
    ) -> WorkItem:
        item_id = f"work-{uuid4().hex[:12]}"
        now = _utc_now_iso()
        self._sub.connection.execute(
            "INSERT INTO work_items (item_id, item_type, title, description, status, "
            "owner_principal_id, origin, parent_item_id, deadline, "
            "dependencies_json, progress_json, context_anchors_json, validation_evidence_json, "
            "urgency, max_sessions, sessions_used, last_session_notes, next_step_hint, "
            "stuck_loop_count, created_at, updated_at, last_activity_at) "
            "VALUES (?, ?, ?, ?, 'pending', ?, ?, ?, ?, '[]', '[]', '[]', '[]', "
            "?, ?, 0, '', '', 0, ?, ?, ?)",
            (
                item_id, item_type, title, description, owner_principal_id, origin,
                parent_item_id, deadline, urgency, int(max_sessions), now, now, now
            ),
        )
        self._sub.connection.commit()
        return self.get(item_id)

    def get(self, item_id: str) -> WorkItem:
        row = self._sub.connection.execute(
            "SELECT item_id, item_type, title, description, status, "
            "owner_principal_id, origin, parent_item_id, deadline, "
            "dependencies_json, progress_json, context_anchors_json, validation_evidence_json, "
            "urgency, max_sessions, sessions_used, last_session_notes, next_step_hint, "
            "stuck_loop_count, created_at, updated_at, last_activity_at "
            "FROM work_items WHERE item_id = ?",
            (item_id,),
        ).fetchone()
        if row is None:
            raise WorkItemNotFoundError(item_id)
        return _row_to_item(row)

    def list_all(self, *, status: str | None = None, item_type: str | None = None, limit: int = 100) -> list[WorkItem]:
        query = "SELECT * FROM work_items WHERE 1=1"
        params = []
        if status:
            query += " AND status = ?"
            params.append(status)
        if item_type:
            query += " AND item_type = ?"
            params.append(item_type)
        query += " ORDER BY last_activity_at DESC LIMIT ?"
        params.append(limit)
        
        cursor = self._sub.connection.execute(query, tuple(params))
        return [_row_to_item(row) for row in cursor.fetchall()]

    def list_open(self) -> list[WorkItem]:
        cursor = self._sub.connection.execute(
            "SELECT * FROM work_items WHERE status IN ('pending', 'in_progress', 'blocked', 'paused') ORDER BY urgency DESC, last_activity_at DESC"
        )
        return [_row_to_item(row) for row in cursor.fetchall()]

    def list_urgent_due_items(self) -> list[WorkItem]:
        all_open = self.list_open()
        return [t for t in all_open if t.is_urgent()]

    def list_recently_failed(self, *, hours: int = 6, limit: int = 5) -> list[WorkItem]:
        """Return tasks that failed within the last ``hours`` hours, most recent first."""
        cursor = self._sub.connection.execute(
            "SELECT * FROM work_items WHERE status = 'failed' "
            "AND updated_at >= datetime('now', ?) "
            "ORDER BY updated_at DESC LIMIT ?",
            (f"-{hours} hours", limit),
        )
        return [_row_to_item(row) for row in cursor.fetchall()]

    def update_status(self, item_id: str, status: WorkItemStatus) -> WorkItem:
        return self._patch(item_id, {"status": status.value})

    def increment_sessions_used(self, item_id: str) -> WorkItem:
        self._sub.connection.execute(
            "UPDATE work_items SET sessions_used = sessions_used + 1, updated_at = ?, last_activity_at = ? WHERE item_id = ?",
            (_utc_now_iso(), _utc_now_iso(), item_id),
        )
        self._sub.connection.commit()
        return self.get(item_id)

    def delete(self, item_id: str) -> bool:
        cursor = self._sub.connection.execute("DELETE FROM work_items WHERE item_id = ?", (item_id,))
        self._sub.connection.commit()
        return cursor.rowcount > 0

    def set_session_handoff(self, item_id: str, *, notes: str = "", next_step: str = "") -> WorkItem:
        return self._patch(
            item_id,
            {
                "last_session_notes": (notes or "")[:4000],
                "next_step_hint": (next_step or "")[:500],
            },
        )

    def append_progress(self, item_id: str, summary: str) -> WorkItem:
        item = self.get(item_id)
        progress = list(item.progress_json)
        progress.append({
            "summary": summary,
            "at": _utc_now_iso(),
        })
        return self._patch(item_id, {"progress_json": json.dumps(progress, ensure_ascii=False)})

    def append_validation_evidence(self, item_id: str, evidence: str) -> WorkItem:
        item = self.get(item_id)
        ev_list = list(item.validation_evidence_json)
        ev_list.append({
            "evidence": evidence,
            "at": _utc_now_iso(),
        })
        return self._patch(item_id, {"validation_evidence_json": json.dumps(ev_list, ensure_ascii=False)})

    def _patch(self, item_id: str, fields: dict[str, Any]) -> WorkItem:
        if not fields:
            return self.get(item_id)
        self.get(item_id)
        cols = ", ".join(f"{k} = ?" for k in fields)
        params = list(fields.values()) + [_utc_now_iso(), _utc_now_iso(), item_id]
        self._sub.connection.execute(
            f"UPDATE work_items SET {cols}, updated_at = ?, last_activity_at = ? WHERE item_id = ?",
            params,
        )
        self._sub.connection.commit()
        return self.get(item_id)


def _row_to_item(row) -> WorkItem:
    return WorkItem(
        item_id=row[0],
        item_type=row[1],
        title=row[2],
        description=row[3],
        status=WorkItemStatus(row[4]),
        owner_principal_id=row[5],
        origin=row[6],
        parent_item_id=row[7],
        deadline=row[8],
        dependencies_json=json.loads(row[9] or "[]"),
        progress_json=json.loads(row[10] or "[]"),
        context_anchors_json=json.loads(row[11] or "[]"),
        validation_evidence_json=json.loads(row[12] or "[]"),
        urgency=row[13],
        max_sessions=int(row[14] or 0),
        sessions_used=int(row[15] or 0),
        last_session_notes=row[16],
        next_step_hint=row[17],
        stuck_loop_count=int(row[18] or 0),
        created_at=row[19],
        updated_at=row[20],
        last_activity_at=row[21],
    )
