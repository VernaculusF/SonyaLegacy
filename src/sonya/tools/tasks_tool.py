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
    ]
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
    ) -> None:
        self._service = TaskService(TaskStore(substrate), stream=stream)
        self._default_principal = default_principal_id

    # ---------- create ----------

    def create(self, arg: str) -> str:
        """Format: title | description | step1; step2; step3 (description and steps optional).

        Examples:
            tasks.create write Discord channel adapter
            tasks.create Refactor planner | extract scoring into own class | read planner.py; design new shape; propose change; validate; apply
        """
        if not arg.strip():
            return "[ERROR] tasks.create needs at least a title"
        parts = [p.strip() for p in arg.split("|")]
        title = parts[0]
        description = parts[1] if len(parts) > 1 else ""
        steps_raw = parts[2] if len(parts) > 2 else ""
        plan_steps = (
            [s.strip() for s in steps_raw.split(";") if s.strip()] if steps_raw else None
        )
        try:
            task = self._service.create(
                title=title,
                description=description,
                principal_id=self._default_principal,
                plan_steps=plan_steps,
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
        """Format: task_id | step1; step2; step3"""
        parts = arg.split("|", 1)
        if len(parts) < 2:
            return "[ERROR] tasks.plan needs: task_id | step1; step2; ..."
        task_id = parts[0].strip()
        steps = [s.strip() for s in parts[1].split(";") if s.strip()]
        if not steps:
            return "[ERROR] tasks.plan needs at least one step"
        try:
            task = self._service.set_plan(task_id, steps)
        except (TaskNotFoundError, ValueError) as err:
            return f"[ERROR] {err}"
        return f"[OK] plan set ({len(steps)} steps)\n{_format_task(task)}"

    def step(self, arg: str) -> str:
        """Format: task_id | step_idx | summary"""
        parts = arg.split("|", 2)
        if len(parts) < 3:
            return "[ERROR] tasks.step needs: task_id | step_idx | summary"
        task_id = parts[0].strip()
        try:
            step_idx = int(parts[1].strip())
        except ValueError:
            return "[ERROR] step_idx must be integer"
        summary = parts[2].strip()
        try:
            task = self._service.mark_step_done(task_id, step_idx, summary)
        except (TaskNotFoundError, ValueError) as err:
            return f"[ERROR] {err}"
        done = len(task.completed_steps)
        total = len(task.plan_steps)
        return f"[OK] step {step_idx} done ({done}/{total})"

    # ---------- terminal ----------

    def complete(self, arg: str) -> str:
        """Format: task_id | result"""
        parts = arg.split("|", 1)
        task_id = parts[0].strip()
        result = parts[1].strip() if len(parts) > 1 else ""
        try:
            task = self._service.complete(task_id, result)
        except (TaskNotFoundError, TaskTransitionError) as err:
            return f"[ERROR] {err}"
        return f"[OK] task done\n{_format_task(task)}"

    def fail(self, arg: str) -> str:
        """Format: task_id | reason"""
        parts = arg.split("|", 1)
        if len(parts) < 2:
            return "[ERROR] tasks.fail needs: task_id | reason"
        try:
            task = self._service.fail(parts[0].strip(), parts[1].strip())
        except (TaskNotFoundError, TaskTransitionError) as err:
            return f"[ERROR] {err}"
        return f"[OK] task failed\n{_format_task(task)}"

    def block(self, arg: str) -> str:
        """Format: task_id | blocker"""
        parts = arg.split("|", 1)
        if len(parts) < 2:
            return "[ERROR] tasks.block needs: task_id | blocker"
        try:
            task = self._service.block(parts[0].strip(), parts[1].strip())
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
