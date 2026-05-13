from sonya_runtime.actions.models import RuntimeTaskPayload
from sonya_runtime.tasks.sqlite_store import SQLiteTaskStore


def _payload(**overrides):
    base = {
        "kind": "workspace_analysis",
        "goal": "Проверить структуру workspace",
        "requested_by_principal": "5785127604",
        "origin_channel": "telegram",
        "origin_chat_id": "5785127604",
        "source_message": "проверь папку",
        "context_summary": "Нужно понять состояние workspace",
        "suggested_steps": ("осмотреть корень",),
        "priority": 4,
        "requires_user_followup": False,
        "followup_prompt": "",
    }
    base.update(overrides)
    return RuntimeTaskPayload(**base)


def test_sqlite_task_store_create_and_read(tmp_path):
    store = SQLiteTaskStore(tmp_path / "tasks.db")
    task = store.create_task(_payload())

    loaded = store.get_task(task.task_id)
    assert loaded is not None
    assert loaded.task_id == task.task_id
    assert loaded.kind == "workspace_analysis"


def test_sqlite_task_store_claim_and_complete(tmp_path):
    store = SQLiteTaskStore(tmp_path / "tasks.db")
    task = store.create_task(_payload())

    claimed = store.claim_next_task("worker-1", {"workspace_analysis"})
    assert claimed is not None
    assert claimed.task_id == task.task_id
    assert claimed.status == "running"

    done = store.mark_done(task.task_id, "Готово", {"files": ["docs/"]})
    assert done is not None
    assert done.status == "done"
    assert done.result_summary == "Готово"
    assert done.result_payload == {"files": ["docs/"]}


def test_sqlite_task_store_prevents_double_claim(tmp_path):
    store = SQLiteTaskStore(tmp_path / "tasks.db")
    store.create_task(_payload())

    first = store.claim_next_task("worker-1", {"workspace_analysis"})
    second = store.claim_next_task("worker-2", {"workspace_analysis"})

    assert first is not None
    assert second is None


def test_sqlite_task_store_filters_open_tasks_for_principal(tmp_path):
    store = SQLiteTaskStore(tmp_path / "tasks.db")
    open_task = store.create_task(_payload(goal="Первая задача"))
    done_task = store.create_task(_payload(goal="Вторая задача"))
    store.claim_next_task("worker-1", {"workspace_analysis"})
    store.mark_done(done_task.task_id, "ok", {})

    open_tasks = store.get_open_tasks_for_principal("5785127604", "5785127604")
    assert [task.task_id for task in open_tasks] == [open_task.task_id]
