import sqlite3

from sonya_runtime.actions.models import RuntimeTaskPayload
from sonya_runtime.storage.paths import RuntimePaths
from sonya_runtime.tasks.sqlite_store import SQLiteTaskStore
from sonya_runtime.tasks.worker import run_worker


def test_worker_processes_pending_task_once(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")

    runtime_paths = RuntimePaths(tmp_path)
    store = SQLiteTaskStore(runtime_paths.tasks_db_path)
    task = store.create_task(
        RuntimeTaskPayload(
            kind="workspace_analysis",
            goal="Проверить структуру workspace",
            requested_by_principal="5785127604",
            origin_channel="telegram",
            origin_chat_id="5785127604",
            source_message="проверь папку",
            context_summary="Нужна сводка",
            suggested_steps=("осмотреть корень",),
            priority=4,
        )
    )
    store.close()

    exit_code = run_worker(tmp_path, once=True, poll_interval=0.01)
    assert exit_code == 0

    reloaded = SQLiteTaskStore(runtime_paths.tasks_db_path)
    done = reloaded.get_task(task.task_id)
    assert done is not None
    assert done.status == "done"
    assert "README.md" in done.result_summary
