import sqlite3
from pathlib import Path

from sonya_runtime.tasks.executor import TaskExecutor
from sonya_runtime.tasks.models import TaskRecord


def _task(kind: str) -> TaskRecord:
    return TaskRecord(
        task_id="task-1",
        kind=kind,
        goal="Проверить состояние проекта",
        context_summary="Нужна краткая сводка",
        source_message="посмотри файлы",
        status="pending",
        priority=3,
        created_at="2026-05-08T00:00:00Z",
        updated_at="2026-05-08T00:00:00Z",
        requested_by_principal="5785127604",
        origin_channel="telegram",
        origin_chat_id="5785127604",
    )


def test_executor_runs_workspace_analysis(tmp_path: Path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "README.md").write_text("hello", encoding="utf-8")
    executor = TaskExecutor(repo_root=tmp_path, openclaw_root=tmp_path)

    result = executor.execute(_task("workspace_analysis"))
    assert "README.md" in result.summary
    assert "README.md" in result.payload["top_entries"]


def test_executor_runs_memory_diagnosis(tmp_path: Path):
    db_dir = tmp_path / "workspace" / "memory_system" / "db"
    db_dir.mkdir(parents=True)
    conn = sqlite3.connect(db_dir / "memory.db")
    conn.executescript(
        """
        CREATE TABLE events(created_at TEXT);
        CREATE TABLE facts(created_at TEXT);
        CREATE TABLE lessons(created_at TEXT);
        CREATE TABLE working_memory(created_at TEXT);
        INSERT INTO events(created_at) VALUES ('2026-05-08T00:00:00Z');
        INSERT INTO facts(created_at) VALUES ('2026-05-08T00:00:01Z');
        INSERT INTO lessons(created_at) VALUES ('2026-05-08T00:00:02Z');
        INSERT INTO working_memory(created_at) VALUES ('2026-05-08T00:00:03Z');
        """
    )
    conn.commit()
    conn.close()

    executor = TaskExecutor(repo_root=tmp_path, openclaw_root=tmp_path)
    result = executor.execute(_task("memory_diagnosis"))
    assert result.payload["working_memory"]["latest_created_at"] == "2026-05-08T00:00:03Z"


def test_executor_rejects_unsupported_kind(tmp_path: Path):
    executor = TaskExecutor(repo_root=tmp_path, openclaw_root=tmp_path)
    try:
        executor.execute(_task("write_random_file"))
    except ValueError as err:
        assert "unsupported task kind" in str(err)
    else:
        raise AssertionError("expected ValueError")
