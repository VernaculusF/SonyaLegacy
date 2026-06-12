"""WorkItemService: business logic on top of WorkItemStore.

Enforces transitions and emits continuity events. Replaces TaskService.
"""
from __future__ import annotations

from sonya.state.continuity_stream import ContinuityEvent, ContinuityStream
from sonya.work.models import WorkItem, WorkItemNotFoundError, WorkItemStatus, WorkItemTransitionError
from sonya.work.store import WorkItemStore


class WorkItemService:
    def __init__(
        self,
        store: WorkItemStore,
        *,
        stream: ContinuityStream | None = None,
    ) -> None:
        self._store = store
        self._stream = stream

    # ---------- create ----------

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
        urgency: str | None = None,
        max_sessions: int = 0,
    ) -> WorkItem:
        if not title.strip():
            raise ValueError("title cannot be empty")
        if max_sessions < 0:
            raise ValueError("max_sessions cannot be negative (0 = unlimited)")

        if urgency is None:
            urgency = "normal" if origin == "ivan" else "background"
        if urgency not in ("urgent", "normal", "background"):
            raise ValueError(f"urgency must be urgent|normal|background, got {urgency!r}")
            
        item = self._store.create(
            title=title,
            item_type=item_type,
            description=description,
            owner_principal_id=owner_principal_id,
            origin=origin,
            parent_item_id=parent_item_id,
            deadline=deadline,
            urgency=urgency,
            max_sessions=max_sessions,
        )
        self._emit("work.created", item, extra={
            "title": item.title,
            "origin": origin,
            "max_sessions": max_sessions,
            "urgency": urgency,
        })
        return item

    def record_session_handoff(
        self,
        item_id: str,
        *,
        notes: str = "",
        next_step: str = "",
    ) -> WorkItem:
        item = self._store.increment_sessions_used(item_id)
        if notes or next_step:
            item = self._store.set_session_handoff(item_id, notes=notes, next_step=next_step)

        if item.session_budget_exhausted() and item.status not in (WorkItemStatus.DONE, WorkItemStatus.FAILED, WorkItemStatus.ARCHIVED):
            failed = self._store.update_status(item_id, WorkItemStatus.FAILED)
            self._emit("work.session_budget_exhausted", failed, extra={
                "sessions_used": failed.sessions_used,
                "max_sessions": failed.max_sessions,
            })
            return failed
            
        self._emit("work.session_handoff", item, extra={
            "sessions_used": item.sessions_used,
            "max_sessions": item.max_sessions,
            "next_step": next_step[:200],
        })
        return item

    # ---------- pickup / pause ----------

    def set_in_progress(self, item_id: str) -> WorkItem:
        item = self._store.get(item_id)
        if item.status in (WorkItemStatus.DONE, WorkItemStatus.FAILED, WorkItemStatus.ARCHIVED):
            raise WorkItemTransitionError(
                f"item {item_id} is {item.status.value}; cannot resume"
            )
        if item.status is WorkItemStatus.IN_PROGRESS:
            return item
        updated = self._store.update_status(item_id, WorkItemStatus.IN_PROGRESS)
        self._emit("work.picked_up", updated)
        return updated

    def pause(self, item_id: str) -> WorkItem:
        item = self._store.get(item_id)
        if item.status in (WorkItemStatus.DONE, WorkItemStatus.FAILED, WorkItemStatus.ARCHIVED):
            return item
        if item.status is WorkItemStatus.PAUSED:
            return item
        updated = self._store.update_status(item_id, WorkItemStatus.PAUSED)
        self._emit("work.paused", updated)
        return updated

    def resume(self, item_id: str) -> WorkItem:
        item = self._store.get(item_id)
        if item.status is not WorkItemStatus.PAUSED:
            return item
        updated = self._store.update_status(item_id, WorkItemStatus.IN_PROGRESS)
        self._emit("work.resumed", updated)
        return updated

    # ---------- progress ----------

    def append_progress(self, item_id: str, summary: str) -> WorkItem:
        updated = self._store.append_progress(item_id, summary)
        self._emit(
            "work.progress_added",
            updated,
            extra={"summary": summary[:200]},
        )
        return updated

    # ---------- terminal ----------

    def complete(self, item_id: str, evidence: str) -> WorkItem:
        item = self._store.get(item_id)
        if item.is_resolved():
            raise WorkItemTransitionError(
                f"item {item_id} already {item.status.value}"
            )
        if evidence:
            self._store.append_validation_evidence(item_id, evidence)
        updated = self._store.update_status(item_id, WorkItemStatus.DONE)
        self._emit("work.completed", updated, extra={"evidence": evidence[:300]})
        return updated

    def fail(self, item_id: str, reason: str) -> WorkItem:
        item = self._store.get(item_id)
        if item.is_resolved():
            raise WorkItemTransitionError(
                f"item {item_id} already {item.status.value}"
            )
        updated = self._store.update_status(item_id, WorkItemStatus.FAILED)
        self._emit("work.failed", updated, extra={"reason": reason[:300]})
        return updated

    def archive(self, item_id: str) -> WorkItem:
        item = self._store.get(item_id)
        if item.status is WorkItemStatus.ARCHIVED:
            return item
        updated = self._store.update_status(item_id, WorkItemStatus.ARCHIVED)
        self._emit("work.archived", updated)
        return updated

    def block(self, item_id: str, blocker: str) -> WorkItem:
        item = self._store.get(item_id)
        if item.is_resolved():
            raise WorkItemTransitionError(
                f"item {item_id} already {item.status.value}; cannot block"
            )
        updated = self._store.update_status(item_id, WorkItemStatus.BLOCKED)
        self._emit("work.blocked", updated, extra={"blocker": blocker[:200]})
        return updated

    def unblock(self, item_id: str) -> WorkItem:
        item = self._store.get(item_id)
        if item.status is not WorkItemStatus.BLOCKED:
            return item
        updated = self._store.update_status(item_id, WorkItemStatus.IN_PROGRESS)
        self._emit("work.unblocked", updated)
        return updated

    # ---------- queries ----------

    def get(self, item_id: str) -> WorkItem:
        return self._store.get(item_id)

    def list_open(self) -> list[WorkItem]:
        return self._store.list_open()

    def list_urgent_due_items(self) -> list[WorkItem]:
        return self._store.list_urgent_due_items()

    def pick_next(self) -> WorkItem | None:
        open_items = self._store.list_open()
        in_progress = [t for t in open_items if t.status is WorkItemStatus.IN_PROGRESS]
        if in_progress:
            return in_progress[0]
        pending = sorted(
            (t for t in open_items if t.status is WorkItemStatus.PENDING),
            key=lambda t: t.created_at,
        )
        if pending:
            return pending[0]
        return None

    # ---------- internals ----------

    def _emit(self, kind: str, item: WorkItem, *, extra: dict | None = None) -> None:
        if self._stream is None:
            return
        payload: dict = {
            "item_id": item.item_id,
            "status": item.status.value,
        }
        if extra:
            payload.update(extra)
        try:
            self._stream.append(ContinuityEvent(
                kind=kind,
                principal_id=item.owner_principal_id,
                payload=payload,
            ))
        except Exception:
            pass
