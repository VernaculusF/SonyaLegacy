"""WorkTool: agent-facing wrapper around WorkItemService.

Replaces TasksTool.
"""
from __future__ import annotations

import json

from sonya.state.continuity_stream import ContinuityStream
from sonya.state.substrate import Substrate
from sonya.work.models import WorkItem, WorkItemNotFoundError, WorkItemTransitionError
from sonya.work.service import WorkItemService
from sonya.work.store import WorkItemStore


def _format_work(item: WorkItem) -> str:
    lines = [
        f"item_id: {item.item_id}",
        f"item_type: {item.item_type}",
        f"title: {item.title}",
        f"status: {item.status.value}",
        f"origin: {item.origin}",
        f"urgency: {item.urgency}",
    ]
    if item.description:
        lines.append(f"description: {item.description}")
    if item.deadline:
        lines.append(f"deadline: {item.deadline}")
    if item.progress_json:
        lines.append("progress:")
        for p in item.progress_json:
            lines.append(f"  - {p.get('summary')} ({p.get('at')})")
    lines.append(f"created: {item.created_at}")
    lines.append(f"updated: {item.updated_at}")
    return "\n".join(lines)


def _format_brief(item: WorkItem) -> str:
    return f"{item.item_id} | {item.status.value:11} | [{item.item_type}] {item.title}"


class WorkTool:
    def __init__(
        self,
        substrate: Substrate,
        *,
        stream: ContinuityStream | None = None,
        default_origin: str = "self",
    ) -> None:
        self._service = WorkItemService(WorkItemStore(substrate), stream=stream)
        self._default_origin = default_origin

    def create(self, arg: str) -> str:
        if not arg.strip():
            return "[ERROR] work.create needs at least a title"
        title = ""
        description = ""
        origin = self._default_origin
        item_type = "task"
        urgency = "normal"
        max_sessions = 0
        stripped = arg.strip()
        if stripped.startswith("{"):
            try:
                data = json.loads(stripped)
                title = data.get("title", "")
                description = data.get("description", "")
                if "origin" in data:
                    origin = str(data.get("origin", "")).strip().lower() or self._default_origin
                if "item_type" in data:
                    item_type = str(data.get("item_type", "task"))
                if "urgency" in data:
                    urgency = str(data.get("urgency", "normal"))
                max_sessions = int(data.get("max_sessions", 0))
            except Exception as e:
                return f"[ERROR] work.create: invalid JSON ({e})"
        else:
            parts = [p.strip() for p in arg.split("|")]
            title = parts[0]
            if len(parts) > 1:
                description = parts[1]
                
        if not title:
            return "[ERROR] work.create: title is required"
        try:
            item = self._service.create(
                title=title,
                description=description,
                origin=origin,
                item_type=item_type,
                urgency=urgency,
                max_sessions=max_sessions,
            )
            return f"[OK] created\n{_format_work(item)}"
        except Exception as e:
            return f"[ERROR] {e}"

    def get(self, arg: str) -> str:
        item_id = arg.strip()
        if not item_id:
            return "[ERROR] specify item_id"
        try:
            item = self._service.get(item_id)
            return _format_work(item)
        except WorkItemNotFoundError:
            return f"[ERROR] not found: {item_id}"
        except Exception as e:
            return f"[ERROR] {e}"

    def list(self, arg: str) -> str:
        try:
            items = self._service.list_open()
            if not items:
                return "[OK] No open work items."
            return "\n".join(_format_brief(t) for t in items)
        except Exception as e:
            return f"[ERROR] {e}"

    def complete(self, arg: str) -> str:
        if not arg.strip():
            return "[ERROR] usage: work.complete <item_id> | <evidence>"
        parts = [p.strip() for p in arg.split("|")]
        item_id = parts[0]
        evidence = parts[1] if len(parts) > 1 else ""
        if not item_id or not evidence:
            return "[ERROR] usage: work.complete <item_id> | <evidence>. Acceptance evidence is mandatory (e.g. proof of completion)."
        try:
            item = self._service.complete(item_id, evidence)
            return f"[OK] completed: {item_id}"
        except Exception as e:
            return f"[ERROR] {e}"

    def fail(self, arg: str) -> str:
        if not arg.strip():
            return "[ERROR] usage: work.fail <item_id> | <reason>"
        parts = [p.strip() for p in arg.split("|")]
        item_id = parts[0]
        reason = parts[1] if len(parts) > 1 else ""
        if not item_id:
            return "[ERROR] usage: work.fail <item_id> | <reason>"
        try:
            item = self._service.fail(item_id, reason)
            return f"[OK] failed: {item_id} (reason: {reason})"
        except Exception as e:
            return f"[ERROR] {e}"

    def block(self, arg: str) -> str:
        if not arg.strip():
            return "[ERROR] usage: work.block <item_id> | <blocker>"
        parts = [p.strip() for p in arg.split("|")]
        item_id = parts[0]
        blocker = parts[1] if len(parts) > 1 else ""
        if not item_id:
            return "[ERROR] usage: work.block <item_id> | <blocker>"
        try:
            item = self._service.block(item_id, blocker)
            return f"[OK] blocked: {item_id} (blocker: {blocker})"
        except Exception as e:
            return f"[ERROR] {e}"

    def unblock(self, arg: str) -> str:
        item_id = arg.strip()
        if not item_id:
            return "[ERROR] usage: work.unblock <item_id>"
        try:
            item = self._service.unblock(item_id)
            return f"[OK] unblocked: {item_id}"
        except Exception as e:
            return f"[ERROR] {e}"

    def pause(self, arg: str) -> str:
        item_id = arg.strip()
        if not item_id:
            return "[ERROR] usage: work.pause <item_id>"
        try:
            item = self._service.pause(item_id)
            return f"[OK] paused: {item_id}"
        except Exception as e:
            return f"[ERROR] {e}"

    def pick(self, arg: str) -> str:
        try:
            item = self._service.pick_next()
            if not item:
                return "[OK] No open work items to pick."
            self._service.set_in_progress(item.item_id)
            return f"[OK] picked: {_format_brief(item)}"
        except Exception as e:
            return f"[ERROR] {e}"

    def handoff(self, arg: str) -> str:
        if not arg.strip():
            return "[ERROR] usage: work.handoff <item_id> | <notes> | <next_step>"
        parts = [p.strip() for p in arg.split("|")]
        item_id = parts[0]
        notes = parts[1] if len(parts) > 1 else ""
        next_step = parts[2] if len(parts) > 2 else ""
        if not item_id:
            return "[ERROR] usage: work.handoff <item_id> | <notes> | <next_step>"
        try:
            item = self._service.record_session_handoff(item_id, notes=notes, next_step=next_step)
            if item.status.value == "failed":
                return f"[OK] handoff recorded, but item failed (budget exhausted): {item_id}"
            return f"[OK] handoff recorded: {item_id}"
        except Exception as e:
            return f"[ERROR] {e}"
