"""TasksTool: agent-facing wrapper around TaskService.

All methods return human-readable strings (no exceptions leak to the LLM).
This is the surface the agent sees as `tasks.*` tools in agent_session.
"""
from __future__ import annotations

import json

from sonya.state.continuity_stream import ContinuityStream
from sonya.state.substrate import Substrate
from sonya.tasks.models import Task, TaskNotFoundError, TaskTransitionError
from sonya.tasks.service import TaskService
from sonya.tasks.store import TaskStore


def _format_task(task: Task) -> str:
    lines = [
        f"task_id: {task.task_id}",
        f"title: {task.title}",
        f"status: {task.status.value}",
        f"created_by: {task.created_by}",
        f"notify_mode: {task.notify_mode}",
    ]
    if task.scheduled_for:
        lines.append(f"scheduled_for: {task.scheduled_for}")
    if task.description:
        lines.append(f"description: {task.description}")
    if task.principal_id:
        lines.append(f"principal: {task.principal_id}")
    if task.deadline:
        lines.append(f"deadline: {task.deadline}")
    if task.plan_steps:
        lines.append("plan:")
        done_idx = {c.get("step_idx") for c in task.completed_steps}
        for i, step in enumerate(task.plan_steps):
            mark = "x" if i in done_idx else " "
            lines.append(f"  [{mark}] {i}. {step}")
    if task.completed_steps:
        lines.append(
            f"completed: {len(task.completed_steps)}/{len(task.plan_steps) or '?'}"
        )
    if task.blocker:
        lines.append(f"blocker: {task.blocker}")
    if task.result:
        lines.append(f"result: {task.result[:300]}")
    lines.append(f"created: {task.created_at}")
    lines.append(f"updated: {task.updated_at}")
    return "\n".join(lines)


def _format_brief(task: Task) -> str:
    suffix = ""
    if task.plan_steps:
        done = len(task.completed_steps)
        suffix = f" [{done}/{len(task.plan_steps)}]"
    return f"{task.task_id} | {task.status.value:11} | {task.title}{suffix}"


class TasksTool:
    """Agent-facing wrapper. All methods return strings."""

    def __init__(
        self,
        substrate: Substrate,
        *,
        stream: ContinuityStream | None = None,
        default_principal_id: str | None = None,
        default_created_by: str = "self",
    ) -> None:
        self._service = TaskService(TaskStore(substrate), stream=stream)
        self._default_principal = default_principal_id
        self._default_created_by = default_created_by

    # ---------- create ----------

    def create(self, arg: str) -> str:
        """Accepts either JSON or pipe-format.

        JSON keys: title, description, plan_steps[], created_by ('ivan'|'self'),
                   scheduled_for (ISO timestamp; empty=now),
                   notify_mode ('progress'|'final'|'silent'),
                   recurring_spec (string; empty=one-off).
        Pipe (legacy): title | description | step1; step2  → defaults to created_by='self'.
        """
        if not arg.strip():
            return "[ERROR] tasks.create needs at least a title"
        title = ""
        description = ""
        plan_steps: list[str] | None = None
        created_by = self._default_created_by
        scheduled_for = ""
        notify_mode = "progress"
        recurring_spec = ""
        # Try JSON first
        stripped = arg.strip()
        if stripped.startswith("{"):
            try:
                data = json.loads(stripped)
                title = str(data.get("title", "")).strip()
                description = str(data.get("description", "")).strip()
                steps_raw = data.get("plan_steps")
                if isinstance(steps_raw, list):
                    plan_steps = [str(s).strip() for s in steps_raw if str(s).strip()]
                if "created_by" in data:
                    created_by = str(data.get("created_by", "")).strip().lower() or self._default_created_by
                scheduled_for = str(data.get("scheduled_for", "")).strip()
                notify_mode = str(data.get("notify_mode", "progress")).strip().lower() or "progress"
                recurring_spec = str(data.get("recurring_spec", "")).strip()
            except json.JSONDecodeError as err:
                return f"[ERROR] tasks.create: invalid JSON ({err})"
        else:
            parts = [p.strip() for p in arg.split("|")]
            title = parts[0]
            description = parts[1] if len(parts) > 1 else ""
            steps_raw = parts[2] if len(parts) > 2 else ""
            plan_steps = (
                [s.strip() for s in steps_raw.split(";") if s.strip()] if steps_raw else None
            )
        if not title:
            return "[ERROR] tasks.create: title is required"
        try:
            task = self._service.create(
                title=title,
                description=description,
                principal_id=self._default_principal,
                plan_steps=plan_steps,
                created_by=created_by,
                scheduled_for=scheduled_for,
                recurring_spec=recurring_spec,
                notify_mode=notify_mode,
            )
        except ValueError as err:
            return f"[ERROR] {err}"
        return f"[OK] created\n{_format_task(task)}"

    # ---------- query ----------

    def list(self, arg: str = "") -> str:
        status_filter = arg.strip() or None
        if status_filter == "open":
            tasks = self._service.list_open()
        else:
            tasks = self._service.list(status=status_filter)
        if not tasks:
            return "(no tasks)"
        return "\n".join(_format_brief(t) for t in tasks)

    def get(self, arg: str) -> str:
        task_id = arg.strip()
        if not task_id:
            return "[ERROR] tasks.get needs task_id"
        try:
            task = self._service.get(task_id)
        except TaskNotFoundError:
            return f"[ERROR] task {task_id} not found"
        return _format_task(task)

    def pick(self, arg: str = "") -> str:
        task = self._service.pick_next()
        if task is None:
            return "(no open task to pick)"
        try:
            task = self._service.set_in_progress(task.task_id)
        except TaskTransitionError as err:
            return f"[ERROR] {err}"
        return f"[OK] picked\n{_format_task(task)}"

    # ---------- planning / progress ----------

    def plan(self, arg: str) -> str:
        """JSON: {"task_id": "...", "steps": ["a","b"]} OR legacy: task_id | step1; step2"""
        stripped = arg.strip()
        task_id = ""
        steps: list[str] = []
        if stripped.startswith("{"):
            try:
                data = json.loads(stripped)
                task_id = str(data.get("task_id", "")).strip()
                raw = data.get("steps")
                if isinstance(raw, list):
                    steps = [str(s).strip() for s in raw if str(s).strip()]
            except json.JSONDecodeError as err:
                return f"[ERROR] tasks.plan: invalid JSON ({err})"
        else:
            parts = arg.split("|", 1)
            if len(parts) < 2:
                return "[ERROR] tasks.plan needs JSON or 'task_id | step1; step2; ...'"
            task_id = parts[0].strip()
            steps = [s.strip() for s in parts[1].split(";") if s.strip()]
        if not task_id:
            return "[ERROR] tasks.plan: task_id required"
        if not steps:
            return "[ERROR] tasks.plan needs at least one step"
        try:
            task = self._service.set_plan(task_id, steps)
        except (TaskNotFoundError, ValueError) as err:
            return f"[ERROR] {err}"
        return f"[OK] plan set ({len(steps)} steps)\n{_format_task(task)}"

    def step(self, arg: str) -> str:
        """JSON: {"task_id": "...", "step_idx": 0, "summary": "..."} OR legacy: task_id | idx | summary"""
        stripped = arg.strip()
        task_id = ""
        step_idx_raw = ""
        summary = ""
        if stripped.startswith("{"):
            try:
                data = json.loads(stripped)
                task_id = str(data.get("task_id", "")).strip()
                step_idx_raw = str(data.get("step_idx", ""))
                summary = str(data.get("summary", "")).strip()
            except json.JSONDecodeError as err:
                return f"[ERROR] tasks.step: invalid JSON ({err})"
        else:
            parts = arg.split("|", 2)
            if len(parts) < 3:
                return "[ERROR] tasks.step needs JSON or 'task_id | step_idx | summary'"
            task_id = parts[0].strip()
            step_idx_raw = parts[1].strip()
            summary = parts[2].strip()
        if not task_id:
            return "[ERROR] tasks.step: task_id required"
        try:
            step_idx = int(step_idx_raw)
        except (ValueError, TypeError):
            return "[ERROR] step_idx must be integer"
        try:
            task = self._service.mark_step_done(task_id, step_idx, summary)
        except (TaskNotFoundError, ValueError) as err:
            return f"[ERROR] {err}"
        done = len(task.completed_steps)
        total = len(task.plan_steps)
        return f"[OK] step {step_idx} done ({done}/{total})"

    # ---------- terminal ----------

    def complete(self, arg: str) -> str:
        """JSON: {"task_id": "...", "result": "..."} OR legacy: task_id | result"""
        stripped = arg.strip()
        task_id = ""
        result = ""
        if stripped.startswith("{"):
            try:
                data = json.loads(stripped)
                task_id = str(data.get("task_id", "")).strip()
                result = str(data.get("result", "")).strip()
            except json.JSONDecodeError as err:
                return f"[ERROR] tasks.complete: invalid JSON ({err})"
        else:
            parts = arg.split("|", 1)
            task_id = parts[0].strip()
            result = parts[1].strip() if len(parts) > 1 else ""
        if not task_id:
            return "[ERROR] tasks.complete: task_id required"
        try:
            task = self._service.complete(task_id, result)
        except (TaskNotFoundError, TaskTransitionError) as err:
            return f"[ERROR] {err}"
        return f"[OK] task done\n{_format_task(task)}"

    def fail(self, arg: str) -> str:
        """JSON: {"task_id": "...", "reason": "..."} OR legacy: task_id | reason"""
        stripped = arg.strip()
        task_id = ""
        reason = ""
        if stripped.startswith("{"):
            try:
                data = json.loads(stripped)
                task_id = str(data.get("task_id", "")).strip()
                reason = str(data.get("reason", "")).strip()
            except json.JSONDecodeError as err:
                return f"[ERROR] tasks.fail: invalid JSON ({err})"
        else:
            parts = arg.split("|", 1)
            if len(parts) < 2:
                return "[ERROR] tasks.fail needs JSON or 'task_id | reason'"
            task_id = parts[0].strip()
            reason = parts[1].strip()
        if not task_id or not reason:
            return "[ERROR] tasks.fail: task_id and reason required"
        try:
            task = self._service.fail(task_id, reason)
        except (TaskNotFoundError, TaskTransitionError) as err:
            return f"[ERROR] {err}"
        return f"[OK] task failed\n{_format_task(task)}"

    def block(self, arg: str) -> str:
        """JSON: {"task_id": "...", "blocker": "..."} OR legacy: task_id | blocker"""
        stripped = arg.strip()
        task_id = ""
        blocker = ""
        if stripped.startswith("{"):
            try:
                data = json.loads(stripped)
                task_id = str(data.get("task_id", "")).strip()
                blocker = str(data.get("blocker", "")).strip()
            except json.JSONDecodeError as err:
                return f"[ERROR] tasks.block: invalid JSON ({err})"
        else:
            parts = arg.split("|", 1)
            if len(parts) < 2:
                return "[ERROR] tasks.block needs JSON or 'task_id | blocker'"
            task_id = parts[0].strip()
            blocker = parts[1].strip()
        if not task_id or not blocker:
            return "[ERROR] tasks.block: task_id and blocker required"
        try:
            task = self._service.block(task_id, blocker)
        except (TaskNotFoundError, TaskTransitionError) as err:
            return f"[ERROR] {err}"
        return f"[OK] task blocked\n{_format_task(task)}"

    def unblock(self, arg: str) -> str:
        task_id = arg.strip()
        try:
            task = self._service.unblock(task_id)
        except TaskNotFoundError as err:
            return f"[ERROR] {err}"
        return f"[OK] unblocked\n{_format_task(task)}"

    def pause(self, arg: str) -> str:
        task_id = arg.strip()
        try:
            task = self._service.pause(task_id)
        except TaskNotFoundError as err:
            return f"[ERROR] {err}"
        return f"[OK] paused\n{_format_task(task)}"
