from sonya_runtime.actions.models import RuntimeAction, RuntimeTaskPayload
from sonya_runtime.tasks.service import TaskService
from sonya_runtime.tasks.sqlite_store import SQLiteTaskStore


def _payload():
    return RuntimeTaskPayload(
        kind="workspace_analysis",
        goal="Проверить структуру workspace",
        requested_by_principal="5785127604",
        origin_channel="telegram",
        origin_chat_id="5785127604",
        source_message="проверь папку",
        context_summary="Нужно понять состояние workspace",
        suggested_steps=("осмотреть корень",),
        priority=4,
        requires_user_followup=False,
        followup_prompt="",
    )


def test_task_service_builds_created_response(tmp_path):
    service = TaskService(SQLiteTaskStore(tmp_path / "tasks.db"))
    task = service.create_task_from_payload(_payload())

    response = service.build_task_created_response(task, "Задачу поставила.")
    assert response.kind == "task_created"
    assert task.task_id in response.text
    assert "workspace_analysis" in response.text


def test_task_service_builds_status_response(tmp_path):
    service = TaskService(SQLiteTaskStore(tmp_path / "tasks.db"))
    task = service.create_task_from_payload(_payload())

    response = service.build_task_status_response("5785127604", "5785127604")
    assert response.kind == "task_update"
    assert task.task_id in response.text


def test_task_service_creates_from_action(tmp_path):
    service = TaskService(SQLiteTaskStore(tmp_path / "tasks.db"))
    task = service.create_task_from_action(
        RuntimeAction(
            type="create_task",
            task_payload=_payload(),
        )
    )
    assert task.goal == "Проверить структуру workspace"
