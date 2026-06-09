"""Project runtime model — substrate-level project entities.

Projects are long-lived activity contexts, NOT tasks.
A project is a protected workspace where Sonya works on sustained
activity WITH Ivan's consent. She must not self-initiate destructive
actions inside a project without explicit approval.

Project policy controls what Sonya is allowed to do autonomously:
  - "consent" = must ask Ivan first
  - "allowed" = can do autonomously
  - "forbidden" = never allowed

Default policy is conservative (self_initiate=false, file_write=consent, shell_run=consent).
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

_DEFAULT_POLICY: dict[str, Any] = {
    "self_initiate": False,
    "file_write": "consent",
    "shell_run": "consent",
    "subagent_spawn": "allowed",
    "web_access": "allowed",
    "selfmod_propose": "allowed",
    "selfmod_apply": "consent",
}

PROJECT_STATUSES = (
    "in_progress",
    "waiting_choice",
    "waiting",
    "completed",
    "cancelled",
)


@dataclass
class Project:
    project_id: str
    title: str
    description: str = ""
    workspace_path: str = ""
    status: str = "in_progress"
    owner_principal_id: str = "ivan"
    policy: dict[str, Any] = field(default_factory=lambda: dict(_DEFAULT_POLICY))
    last_activity_at: str = ""
    created_at: str = ""
    updated_at: str = ""

    def policy_allows(self, action: str) -> bool:
        val = self.policy.get(action, "consent")
        return val == "allowed"

    def policy_requires_consent(self, action: str) -> bool:
        val = self.policy.get(action, "consent")
        return val == "consent"

    def policy_forbids(self, action: str) -> bool:
        val = self.policy.get(action, "consent")
        return val == "forbidden"


class ProjectStore:
    def __init__(self, substrate: Any) -> None:
        self._conn = substrate.connection

    _SELF_TOUCH_PATHS = (
        "/sonya/", "\\sonya\\",
        "src/sonya/", "src\\sonya\\",
        ".sonya/", ".sonya\\",
    )

    def create(self, title: str, *, description: str = "",
               workspace_path: str = "",
               owner_principal_id: str = "ivan",
               policy: dict[str, Any] | None = None) -> Project:
        for marker in self._SELF_TOUCH_PATHS:
            if marker in workspace_path.replace("\\", "/").lower():
                raise ValueError(
                    f"Cannot create project pointing at Sonya's own code path "
                    f"('{workspace_path}'). Self-modification must go through "
                    f"the selfmod pipeline, not project workspace."
                )
        now = datetime.now(timezone.utc).isoformat()
        pid = f"proj-{uuid.uuid4().hex[:10]}"
        pol = json.dumps(policy or dict(_DEFAULT_POLICY), ensure_ascii=False)
        self._conn.execute(
            "INSERT INTO projects "
            "(project_id, title, description, workspace_path, status, "
            "owner_principal_id, policy_json, last_activity_at, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, 'in_progress', ?, ?, ?, ?, ?)",
            (pid, title, description, workspace_path,
             owner_principal_id, pol, now, now, now),
        )
        self._conn.commit()
        return self.get(pid)

    def get(self, project_id: str) -> Project:
        row = self._conn.execute(
            "SELECT project_id, title, description, workspace_path, status, "
            "owner_principal_id, policy_json, last_activity_at, created_at, updated_at "
            "FROM projects WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        if row is None:
            raise ProjectNotFoundError(project_id)
        return self._row_to_project(row)

    def list_all(self, *, status: str = "") -> list[Project]:
        if status:
            rows = self._conn.execute(
                "SELECT project_id, title, description, workspace_path, status, "
                "owner_principal_id, policy_json, last_activity_at, created_at, updated_at "
                "FROM projects WHERE status = ? ORDER BY last_activity_at DESC",
                (status,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT project_id, title, description, workspace_path, status, "
                "owner_principal_id, policy_json, last_activity_at, created_at, updated_at "
                "FROM projects ORDER BY last_activity_at DESC",
            ).fetchall()
        return [self._row_to_project(r) for r in rows]

    def update(self, project_id: str, **kwargs: Any) -> Project:
        now = datetime.now(timezone.utc).isoformat()
        sets: list[str] = ["updated_at = ?"]
        vals: list[Any] = [now]
        for k, v in kwargs.items():
            if k == "status":
                raise ValueError("Use ProjectStore.set_status() for status transitions")
            if k == "policy":
                sets.append("policy_json = ?")
                vals.append(json.dumps(v, ensure_ascii=False))
            elif k in ("title", "description", "workspace_path", "owner_principal_id", "last_activity_at"):
                sets.append(f"{k} = ?")
                vals.append(v)
        vals.append(project_id)
        self._conn.execute(
            f"UPDATE projects SET {', '.join(sets)} WHERE project_id = ?",
            vals,
        )
        self._conn.commit()
        return self.get(project_id)

    def set_status(self, project_id: str, status: str, *, reason: str = "",
                   source: str = "runtime") -> Project:
        if status not in PROJECT_STATUSES:
            raise ValueError(
                f"Invalid project status '{status}'. Allowed: {', '.join(PROJECT_STATUSES)}"
            )
        project = self.get(project_id)
        if project.status == status:
            return project
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "UPDATE projects SET status = ?, last_activity_at = ?, updated_at = ? "
            "WHERE project_id = ?",
            (status, now, now, project_id),
        )
        self._conn.commit()
        updated = self.get(project_id)
        payload = {
            "project_id": project_id,
            "title": project.title,
            "from_status": project.status,
            "to_status": status,
            "reason": reason,
            "source": source,
        }
        self._conn.execute(
            "INSERT INTO continuity_events "
            "(kind, channel, payload_json, created_at) VALUES (?, ?, ?, ?)",
            (
                "project.status_changed",
                "worker_log",
                json.dumps(payload, ensure_ascii=False),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        self._conn.commit()
        return updated

    def touch(self, project_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "UPDATE projects SET last_activity_at = ?, updated_at = ? WHERE project_id = ?",
            (now, now, project_id),
        )
        self._conn.commit()

    def delete(self, project_id: str) -> None:
        self._conn.execute("DELETE FROM execution_traces WHERE project_id = ?", (project_id,))
        self._conn.execute("DELETE FROM project_runs WHERE project_id = ?", (project_id,))
        self._conn.execute("DELETE FROM workspace_policy WHERE workspace_id = ?", (project_id,))
        self._conn.execute("DELETE FROM projects WHERE project_id = ?", (project_id,))
        self._conn.commit()

    @staticmethod
    def _row_to_project(row: tuple) -> Project:
        try:
            policy = json.loads(row[6] or "{}")
        except Exception:
            policy = dict(_DEFAULT_POLICY)
        return Project(
            project_id=row[0], title=row[1], description=row[2],
            workspace_path=row[3], status=row[4],
            owner_principal_id=row[5], policy=policy,
            last_activity_at=row[7], created_at=row[8], updated_at=row[9],
        )


class ProjectNotFoundError(Exception):
    pass


@dataclass
class ProjectRun:
    run_id: str
    project_id: str
    kind: str = "main"
    status: str = "pending"
    agent_type: str = ""
    summary: str = ""
    steps: list[dict[str, Any]] = field(default_factory=list)
    result: str = ""
    error: str = ""
    started_at: str = ""
    completed_at: str = ""
    continuity_seq_start: int = 0
    continuity_seq_end: int = 0
    created_at: str = ""


class ProjectRunStore:
    def __init__(self, substrate: Any) -> None:
        self._conn = substrate.connection

    def create(self, project_id: str, *, kind: str = "main",
               agent_type: str = "", continuity_seq_start: int = 0) -> ProjectRun:
        now = datetime.now(timezone.utc).isoformat()
        rid = f"run-{uuid.uuid4().hex[:10]}"
        self._conn.execute(
            "INSERT INTO project_runs "
            "(run_id, project_id, kind, status, agent_type, "
            "continuity_seq_start, created_at) "
            "VALUES (?, ?, ?, 'pending', ?, ?, ?)",
            (rid, project_id, kind, agent_type, continuity_seq_start, now),
        )
        self._conn.commit()
        return self.get(rid)

    def get(self, run_id: str) -> ProjectRun:
        row = self._conn.execute(
            "SELECT run_id, project_id, kind, status, agent_type, summary, "
            "steps_json, result, error, started_at, completed_at, "
            "continuity_seq_start, continuity_seq_end, created_at "
            "FROM project_runs WHERE run_id = ?",
            (run_id,),
        ).fetchone()
        if row is None:
            raise RunNotFoundError(run_id)
        return self._row_to_run(row)

    def list_by_project(self, project_id: str, *, kind: str = "",
                        limit: int = 50) -> list[ProjectRun]:
        if kind:
            rows = self._conn.execute(
                "SELECT run_id, project_id, kind, status, agent_type, summary, "
                "steps_json, result, error, started_at, completed_at, "
                "continuity_seq_start, continuity_seq_end, created_at "
                "FROM project_runs WHERE project_id = ? AND kind = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (project_id, kind, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT run_id, project_id, kind, status, agent_type, summary, "
                "steps_json, result, error, started_at, completed_at, "
                "continuity_seq_start, continuity_seq_end, created_at "
                "FROM project_runs WHERE project_id = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (project_id, limit),
            ).fetchall()
        return [self._row_to_run(r) for r in rows]

    def update(self, run_id: str, **kwargs: Any) -> ProjectRun:
        sets: list[str] = []
        vals: list[Any] = []
        for k, v in kwargs.items():
            if k == "steps":
                sets.append("steps_json = ?")
                vals.append(json.dumps(v, ensure_ascii=False))
            elif k in ("status", "summary", "result", "error",
                       "started_at", "completed_at",
                       "continuity_seq_end", "agent_type"):
                sets.append(f"{k} = ?")
                vals.append(v)
        if not sets:
            return self.get(run_id)
        vals.append(run_id)
        self._conn.execute(
            f"UPDATE project_runs SET {', '.join(sets)} WHERE run_id = ?",
            vals,
        )
        self._conn.commit()
        return self.get(run_id)

    def start(self, run_id: str) -> ProjectRun:
        now = datetime.now(timezone.utc).isoformat()
        return self.update(run_id, status="running", started_at=now)

    def complete(self, run_id: str, *, result: str = "", error: str = "") -> ProjectRun:
        now = datetime.now(timezone.utc).isoformat()
        status = "completed" if not error else "failed"
        return self.update(run_id, status=status, result=result, error=error, completed_at=now)

    @staticmethod
    def _row_to_run(row: tuple) -> ProjectRun:
        try:
            steps = json.loads(row[6] or "[]")
        except Exception:
            steps = []
        return ProjectRun(
            run_id=row[0], project_id=row[1], kind=row[2], status=row[3],
            agent_type=row[4], summary=row[5], steps=steps,
            result=row[7], error=row[8], started_at=row[9],
            completed_at=row[10], continuity_seq_start=row[11],
            continuity_seq_end=row[12], created_at=row[13],
        )


class RunNotFoundError(Exception):
    pass


@dataclass
class ExecutionTrace:
    trace_id: int
    run_id: str
    project_id: str
    step_seq: int
    step_type: str
    content: str
    tool_name: str = ""
    tool_arg_summary: str = ""
    outcome: str = ""
    model: str = ""
    provider: str = ""
    latency_ms: int = 0
    created_at: str = ""


class ExecutionTraceStore:
    def __init__(self, substrate: Any) -> None:
        self._conn = substrate.connection

    def append(self, run_id: str, project_id: str, *,
               step_seq: int, step_type: str, content: str,
               tool_name: str = "", tool_arg_summary: str = "",
               outcome: str = "", model: str = "", provider: str = "",
               latency_ms: int = 0) -> ExecutionTrace:
        now = datetime.now(timezone.utc).isoformat()
        cur = self._conn.execute(
            "INSERT INTO execution_traces "
            "(run_id, project_id, step_seq, step_type, content, "
            "tool_name, tool_arg_summary, outcome, model, provider, "
            "latency_ms, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (run_id, project_id, step_seq, step_type, content,
             tool_name, tool_arg_summary, outcome, model, provider,
             latency_ms, now),
        )
        self._conn.commit()
        tid = cur.lastrowid
        return ExecutionTrace(
            trace_id=tid, run_id=run_id, project_id=project_id,
            step_seq=step_seq, step_type=step_type, content=content,
            tool_name=tool_name, tool_arg_summary=tool_arg_summary,
            outcome=outcome, model=model, provider=provider,
            latency_ms=latency_ms, created_at=now,
        )

    def list_by_run(self, run_id: str, *, limit: int = 200) -> list[ExecutionTrace]:
        rows = self._conn.execute(
            "SELECT trace_id, run_id, project_id, step_seq, step_type, content, "
            "tool_name, tool_arg_summary, outcome, model, provider, latency_ms, created_at "
            "FROM execution_traces WHERE run_id = ? "
            "ORDER BY step_seq ASC LIMIT ?",
            (run_id, limit),
        ).fetchall()
        return [self._row_to_trace(r) for r in rows]

    def list_by_project(self, project_id: str, *, step_type: str = "",
                        limit: int = 200) -> list[ExecutionTrace]:
        if step_type:
            rows = self._conn.execute(
                "SELECT trace_id, run_id, project_id, step_seq, step_type, content, "
                "tool_name, tool_arg_summary, outcome, model, provider, latency_ms, created_at "
                "FROM execution_traces WHERE project_id = ? AND step_type = ? "
                "ORDER BY step_seq DESC LIMIT ?",
                (project_id, step_type, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT trace_id, run_id, project_id, step_seq, step_type, content, "
                "tool_name, tool_arg_summary, outcome, model, provider, latency_ms, created_at "
                "FROM execution_traces WHERE project_id = ? "
                "ORDER BY step_seq DESC LIMIT ?",
                (project_id, limit),
            ).fetchall()
        return [self._row_to_trace(r) for r in rows]

    @staticmethod
    def _row_to_trace(row: tuple) -> ExecutionTrace:
        return ExecutionTrace(
            trace_id=row[0], run_id=row[1], project_id=row[2],
            step_seq=row[3], step_type=row[4], content=row[5],
            tool_name=row[6], tool_arg_summary=row[7],
            outcome=row[8], model=row[9], provider=row[10],
            latency_ms=row[11], created_at=row[12],
        )


@dataclass
class WorkspacePolicy:
    workspace_id: str
    policy: dict[str, Any] = field(default_factory=dict)
    full_system_access: bool = False
    allowed_paths: str = ""
    denied_paths: str = ""
    updated_at: str = ""


class WorkspacePolicyStore:
    def __init__(self, substrate: Any) -> None:
        self._conn = substrate.connection

    def get(self, workspace_id: str) -> WorkspacePolicy:
        row = self._conn.execute(
            "SELECT workspace_id, policy_json, full_system_access, "
            "allowed_paths, denied_paths, updated_at "
            "FROM workspace_policy WHERE workspace_id = ?",
            (workspace_id,),
        ).fetchone()
        if row is None:
            return WorkspacePolicy(workspace_id=workspace_id)
        return WorkspacePolicy(
            workspace_id=row[0],
            policy=json.loads(row[1] or "{}"),
            full_system_access=bool(row[2]),
            allowed_paths=row[3] or "",
            denied_paths=row[4] or "",
            updated_at=row[5] or "",
        )

    def set(self, wp: WorkspacePolicy) -> None:
        now = datetime.now(timezone.utc).isoformat()
        pol = json.dumps(wp.policy, ensure_ascii=False)
        self._conn.execute(
            "INSERT OR REPLACE INTO workspace_policy "
            "(workspace_id, policy_json, full_system_access, "
            "allowed_paths, denied_paths, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (wp.workspace_id, pol, int(wp.full_system_access),
             wp.allowed_paths, wp.denied_paths, now),
        )
        self._conn.commit()

    def set_full_system_access(self, workspace_id: str, enabled: bool) -> None:
        wp = self.get(workspace_id)
        wp.full_system_access = enabled
        if enabled:
            wp.policy = {k: "allowed" for k in (
                "self_initiate", "file_write", "shell_run",
                "subagent_spawn", "web_access",
                "selfmod_propose", "selfmod_apply",
            )}
        else:
            wp.policy = dict(_DEFAULT_POLICY)
        self.set(wp)
