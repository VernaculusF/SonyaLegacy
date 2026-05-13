from __future__ import annotations

from dataclasses import dataclass

from sonya_runtime.actions.models import RuntimeAction, RuntimeTaskPayload
from sonya_runtime.continuity.canonical_response import CanonicalResponse
from sonya_runtime.tasks.models import TaskRecord
from sonya_runtime.tasks.store import TaskStore


@dataclass(slots=True)
class TaskService:
    store: TaskStore

    def create_task_from_payload(self, payload: RuntimeTaskPayload) -> TaskRecord:
        return self.store.create_task(payload)

    def create_task_from_action(self, action: RuntimeAction) -> TaskRecord:
        if action.task_payload is None:
            raise ValueError("task action requires task_payload")
        return self.store.create_task(action.task_payload)

    def build_task_created_response(self, task: TaskRecord, reply_text: str = "") -> CanonicalResponse:
        base = reply_text.strip() or f"Задачу зафиксировала. ID: {task.task_id}."
        text = f"{base}\n\nСтатус: {task.status}\nTask ID: {task.task_id}\nТип: {task.kind}"
        return CanonicalResponse(kind="task_created", text=text, task_ref=task.task_id)

    def build_task_status_response(self, principal_id: str, origin_chat_id: str | None = None) -> CanonicalResponse:
        open_tasks = self.store.get_open_tasks_for_principal(principal_id, origin_chat_id)
        if open_tasks:
            lines = ["Текущие задачи:"]
            for task in open_tasks[:5]:
                lines.append(f"- {task.task_id}: {task.kind} [{task.status}] {task.goal}")
            return CanonicalResponse(kind="task_update", text="\n".join(lines), task_ref=open_tasks[0].task_id)

        recent = self.store.get_recent_tasks_for_principal(principal_id, origin_chat_id, limit=5)  # type: ignore[attr-defined]
        if not recent:
            return CanonicalResponse(kind="task_update", text="У тебя сейчас нет активных задач.")
        latest = recent[0]
        lines = [
            f"Последняя задача: {latest.task_id}",
            f"Статус: {latest.status}",
            f"Цель: {latest.goal}",
        ]
        if latest.result_summary:
            lines.append(f"Результат: {latest.result_summary}")
        if latest.error_text:
            lines.append(f"Ошибка: {latest.error_text}")
        kind = "task_result" if latest.status == "done" else "task_update"
        return CanonicalResponse(kind=kind, text="\n".join(lines), task_ref=latest.task_id)

    def build_task_result_response(self, task: TaskRecord) -> CanonicalResponse:
        lines = [
            f"Задача {task.task_id} завершена.",
            f"Тип: {task.kind}",
            f"Цель: {task.goal}",
        ]
        if task.result_summary:
            lines.append(f"Результат: {task.result_summary}")
        return CanonicalResponse(kind="task_result", text="\n".join(lines), task_ref=task.task_id)
