from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from sonya_runtime.tasks.models import TaskRecord


ALLOWED_TASK_KINDS = {
    "workspace_analysis",
    "documentation_synthesis",
    "lead_workflow_analysis",
    "memory_diagnosis",
    "file_search_and_summary",
}


@dataclass(slots=True)
class TaskExecutionResult:
    summary: str
    payload: dict


@dataclass(slots=True)
class TaskExecutor:
    repo_root: Path
    openclaw_root: Path

    def execute(self, task: TaskRecord) -> TaskExecutionResult:
        if task.kind not in ALLOWED_TASK_KINDS:
            raise ValueError(f"unsupported task kind: {task.kind}")
        handler = getattr(self, f"_execute_{task.kind}")
        return handler(task)

    def _execute_workspace_analysis(self, task: TaskRecord) -> TaskExecutionResult:
        top = sorted(self.repo_root.iterdir(), key=lambda item: item.name.lower())
        names = [item.name for item in top[:12]]
        summary = f"Осмотрела корень проекта. Ключевые узлы: {', '.join(names)}."
        return TaskExecutionResult(summary=summary, payload={"top_entries": names})

    def _execute_documentation_synthesis(self, task: TaskRecord) -> TaskExecutionResult:
        docs_root = self.repo_root / "docs"
        docs = sorted(docs_root.rglob("*.md"))
        titles = []
        for path in docs[:12]:
            title = path.stem
            try:
                for line in path.read_text(encoding="utf-8-sig").splitlines():
                    stripped = line.strip()
                    if stripped.startswith("#"):
                        title = stripped.lstrip("#").strip()
                        break
            except Exception:
                pass
            titles.append({"path": str(path.relative_to(self.repo_root)), "title": title})
        summary = f"Собрала сводку по документации: {len(docs)} markdown-файлов, ключевые разделы перечислены в payload."
        return TaskExecutionResult(summary=summary, payload={"documents": titles, "count": len(docs)})

    def _execute_lead_workflow_analysis(self, task: TaskRecord) -> TaskExecutionResult:
        hits: list[str] = []
        keywords = ("lead", "лид", "crm", "sales", "strategy")
        for path in self.repo_root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".md", ".py", ".json", ".txt"}:
                continue
            try:
                text = path.read_text(encoding="utf-8-sig", errors="ignore").lower()
            except Exception:
                continue
            if any(keyword in text for keyword in keywords):
                hits.append(str(path.relative_to(self.repo_root)))
            if len(hits) >= 15:
                break
        summary = "Проверила, где в проекте всплывают лиды, CRM и sales-поток, и собрала релевантные файлы."
        return TaskExecutionResult(summary=summary, payload={"matching_files": hits})

    def _execute_memory_diagnosis(self, task: TaskRecord) -> TaskExecutionResult:
        db_path = self.openclaw_root / "workspace" / "memory_system" / "db" / "memory.db"
        conn = sqlite3.connect(db_path)
        try:
            cur = conn.cursor()
            tables = ["events", "facts", "lessons", "working_memory"]
            latest = {}
            for table in tables:
                row = cur.execute(f"SELECT MAX(rowid), MAX(created_at) FROM {table}").fetchone()
                latest[table] = {"max_rowid": row[0], "latest_created_at": row[1]}
        finally:
            conn.close()
        summary = "Проверила свежесть memory.db по основным таблицам."
        return TaskExecutionResult(summary=summary, payload=latest)

    def _execute_file_search_and_summary(self, task: TaskRecord) -> TaskExecutionResult:
        query = " ".join(filter(None, [task.goal, task.context_summary, task.source_message])).lower()
        terms = [term for term in {part.strip(" ,.!?") for part in query.split()} if len(term) >= 4][:6]
        matches: list[dict[str, str]] = []
        for path in self.repo_root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in {".md", ".py", ".json", ".txt"}:
                continue
            try:
                text = path.read_text(encoding="utf-8-sig", errors="ignore")
            except Exception:
                continue
            lowered = text.lower()
            if terms and not any(term in lowered for term in terms):
                continue
            snippet = ""
            for line in text.splitlines():
                if any(term in line.lower() for term in terms):
                    snippet = line.strip()
                    break
            matches.append({"path": str(path.relative_to(self.repo_root)), "snippet": snippet[:200]})
            if len(matches) >= 12:
                break
        summary = "Сделала поиск по файлам и собрала релевантные совпадения."
        return TaskExecutionResult(summary=summary, payload={"terms": terms, "matches": matches})
