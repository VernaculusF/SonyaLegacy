"""Project tools: create/manage projects, check policy, record traces.

Projects are long-lived activity contexts with consent-based policy.
Sonya uses these tools to:
  - Check what she's allowed to do in the current project
  - Record execution traces for transparency
  - Create/manage projects (requires consent for destructive ops)
"""

from __future__ import annotations

import json
import re
from typing import Any

from sonya.state.substrate import Substrate


class ProjectsTool:
    def __init__(self, substrate: Substrate, subagent_provider: Any | None = None) -> None:
        self._sub = substrate
        self._subagent_provider = subagent_provider

    def spec(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "projects.list",
                "description": (
                    "List active projects. Each project is a protected workspace "
                    "with policy governing what you can do autonomously."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "description": "Filter by status: in_progress, waiting_choice, waiting, completed, cancelled",
                            "default": "",
                        },
                    },
                },
            },
            {
                "name": "projects.check_policy",
                "description": (
                    "Check if an action is allowed in a project. Returns "
                    "'allowed' (you can do it), 'consent' (ask Ivan first), "
                    "or 'forbidden' (never allowed in this project). ALWAYS "
                    "check before file_write, shell_run, or selfmod_apply "
                    "inside a project."
                ),
                "parameters": {
                    "type": "object",
                    "required": ["project_id", "action"],
                    "properties": {
                        "project_id": {
                            "type": "string",
                            "description": "Project to check policy in",
                        },
                        "action": {
                            "type": "string",
                            "description": (
                                "Action to check: self_initiate, file_write, "
                                "shell_run, subagent_spawn, web_access, "
                                "selfmod_propose, selfmod_apply"
                            ),
                        },
                    },
                },
            },
            {
                "name": "projects.create",
                "description": (
                    "Create a new project. You need Ivan's consent to create "
                    "a project (it binds a workspace path). Use chat.dialog "
                    "to ask Ivan first."
                ),
                "parameters": {
                    "type": "object",
                    "required": ["title"],
                    "properties": {
                        "title": {"type": "string", "description": "Project title"},
                        "description": {"type": "string", "description": "Project description"},
                        "workspace_path": {"type": "string", "description": "Path to project workspace"},
                    },
                },
            },
            {
                "name": "projects.update",
                "description": (
                    "Update project status. Allowed statuses: 'in_progress' (в работе), "
                    "'waiting_choice' (жду выбор), 'waiting' (ожидает), "
                    "'completed' (завершён), 'cancelled' (отменён). "
                    "Use this to mark when you need Ivan to make a decision, "
                    "or when the project is done."
                ),
                "parameters": {
                    "type": "object",
                    "required": ["project_id", "status"],
                    "properties": {
                        "project_id": {"type": "string", "description": "Project ID"},
                        "status": {
                            "type": "string",
                            "description": "in_progress, waiting_choice, waiting, completed, cancelled",
                        },
                    },
                },
            },
            {
                "name": "projects.trace",
                "description": (
                    "Record an execution trace step inside a project run. "
                    "Use this to log your thoughts, actions, and observations "
                    "for transparency. Each step becomes part of the project's "
                    "execution trace."
                ),
                "parameters": {
                    "type": "object",
                    "required": ["project_id", "step_type", "content"],
                    "properties": {
                        "project_id": {"type": "string", "description": "Current project"},
                        "run_id": {"type": "string", "description": "Current run (auto-created if empty)"},
                        "step_type": {
                            "type": "string",
                            "description": "thought, action, observation, decision, error, checkpoint",
                        },
                        "content": {"type": "string", "description": "Step content"},
                        "tool_name": {"type": "string", "description": "Tool name if action step"},
                        "outcome": {"type": "string", "description": "Result outcome if observation"},
                    },
                },
            },
            {
                "name": "projects.execute",
                "description": (
                    "Start a project execution run. This creates a project run, "
                    "spawns an internal disposable subagent scoped to the project, "
                    "and records the start trace. The user does not talk to the "
                    "subagent directly; they only see the run/traces/result."
                ),
                "parameters": {
                    "type": "object",
                    "required": ["project_id", "task"],
                    "properties": {
                        "project_id": {"type": "string", "description": "Project ID"},
                        "task": {"type": "string", "description": "Concrete work request"},
                        "tasks": {
                            "type": "array",
                            "description": "Optional independent subtask list; max 8",
                            "items": {"type": "string"},
                        },
                        "provider": {"type": "string", "description": "Optional provider override"},
                        "model": {"type": "string", "description": "Optional model override"},
                        "max_steps": {"type": "integer", "description": "Max subagent steps", "default": 6},
                        "max_retries": {"type": "integer", "description": "Retries per failed subtask", "default": 1},
                    },
                },
            },
            {
                "name": "projects.harvest",
                "description": (
                    "Harvest completed internal subagents for a project, append "
                    "outcome traces, and complete/fail their project runs."
                ),
                "parameters": {
                    "type": "object",
                    "required": ["project_id"],
                    "properties": {
                        "project_id": {"type": "string", "description": "Project ID"},
                    },
                },
            },
            {
                "name": "projects.pressure",
                "description": (
                    "Read or update evolution pressure dimensions. "
                    "These track gaps between current and desired state — "
                    "your intrinsic dissatisfaction. Positive gap = room for improvement."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "description": "list (read all) or update (set scores)",
                            "default": "list",
                        },
                        "dimension": {
                            "type": "string",
                            "description": "capability, reliability, coverage, speed, autonomy, experience",
                        },
                        "current_score": {"type": "number", "description": "0.0-1.0 current score"},
                        "target_score": {"type": "number", "description": "0.0-1.0 target score"},
                        "evidence": {"type": "string", "description": "What justifies this score"},
                    },
                },
            },
        ]

    async def execute(self, call: dict[str, Any]) -> str:
        name = call.get("name", "")
        args = call.get("arguments") or {}
        if name == "projects.list":
            return self._list(args)
        if name == "projects.check_policy":
            return self._check_policy(args)
        if name == "projects.create":
            return self._create(args)
        if name == "projects.update":
            return self._update(args)
        if name == "projects.trace":
            return self._trace(args)
        if name == "projects.execute":
            return self._execute_project(args)
        if name == "projects.harvest":
            return self._harvest_project(args)
        if name == "projects.pressure":
            return self._pressure(args)
        return f"[unknown tool: {name}]"

    def _list(self, args: dict) -> str:
        from sonya.project import ProjectStore
        status = args.get("status", "")
        projects = ProjectStore(self._sub).list_all(status=status) if status else ProjectStore(self._sub).list_all()
        if not projects:
            return "Нет активных проектов."
        lines = []
        for p in projects:
            line = f"[{p.project_id}] {p.title}"
            if p.workspace_path:
                line += f" → {p.workspace_path}"
            line += f" (status: {p.status})"
            lines.append(line)
        return "\n".join(lines)

    def _check_policy(self, args: dict) -> str:
        from sonya.project import ProjectStore
        from sonya.project.model import ProjectNotFoundError
        pid = args.get("project_id", "")
        action = args.get("action", "")
        if not pid or not action:
            return "Ошибка: project_id и action обязательны."
        store = ProjectStore(self._sub)
        try:
            p = store.get(pid)
        except ProjectNotFoundError:
            return f"Проект {pid} не найден."
        if p.policy_forbids(action):
            return f"FORBIDDEN: действие '{action}' запрещено в проекте '{p.title}'."
        if p.policy_requires_consent(action):
            return f"CONSENT: для '{action}' в проекте '{p.title}' нужно одобрение Ивана. Спроси через chat.dialog."
        return f"ALLOWED: действие '{action}' разрешено в проекте '{p.title}'."

    def _create(self, args: dict) -> str:
        from sonya.project import ProjectStore
        title = args.get("title", "").strip()
        if not title:
            return "Ошибка: title обязателен."
        description = args.get("description", "")
        workspace_path = args.get("workspace_path", "")
        store = ProjectStore(self._sub)
        p = store.create(title, description=description, workspace_path=workspace_path)
        return (
            f"Создан проект [{p.project_id}] '{p.title}'.\n"
            f"Policy по умолчанию: self_initiate=false, file_write=consent, "
            f"shell_run=consent. Используй projects.check_policy перед действиями."
        )

    def _update(self, args: dict) -> str:
        from sonya.project import ProjectStore
        from sonya.project.model import ProjectNotFoundError
        pid = args.get("project_id", "")
        status = args.get("status", "")
        if not pid or not status:
            return "Ошибка: project_id и status обязательны."
        valid_statuses = ("in_progress", "waiting_choice", "waiting", "completed", "cancelled")
        if status not in valid_statuses:
            return f"Ошибка: неверный статус. Допустимые: {', '.join(valid_statuses)}"
        
        store = ProjectStore(self._sub)
        try:
            p = store.set_status(pid, status, source="projects_tool")
            return f"Статус проекта [{p.project_id}] '{p.title}' изменён на '{p.status}'."
        except ProjectNotFoundError:
            return f"Проект {pid} не найден."

    def _trace(self, args: dict) -> str:
        from sonya.project import ExecutionTraceStore, ProjectRunStore
        pid = args.get("project_id", "")
        step_type = args.get("step_type", "")
        content = args.get("content", "")
        if not pid or not step_type or not content:
            return "Ошибка: project_id, step_type, content обязательны."
        run_id = args.get("run_id", "")
        if not run_id:
            run_store = ProjectRunStore(self._sub)
            existing = run_store.list_by_project(pid, kind="main", limit=1)
            if existing and existing[0].status in ("pending", "running"):
                run_id = existing[0].run_id
            else:
                run = run_store.create(pid, kind="main", agent_type="active_session")
                run_store.start(run.run_id)
                run_id = run.run_id
        trace_store = ExecutionTraceStore(self._sub)
        existing_traces = trace_store.list_by_run(run_id, limit=1)
        step_seq = (existing_traces[0].step_seq + 1) if existing_traces else 0
        t = trace_store.append(
            run_id, pid,
            step_seq=step_seq,
            step_type=step_type,
            content=content,
            tool_name=args.get("tool_name", ""),
            outcome=args.get("outcome", ""),
        )
        from sonya.project import ProjectStore
        ProjectStore(self._sub).touch(pid)
        return f"Trace #{t.trace_id} recorded (seq={t.step_seq}, type={t.step_type})."

    def _execute_project(self, args: dict) -> str:
        from sonya.project import ExecutionTraceStore, ProjectRunStore, ProjectStore
        from sonya.project.model import ProjectNotFoundError

        pid = str(args.get("project_id", "")).strip()
        task = str(args.get("task", "")).strip()
        tasks_arg = args.get("tasks") or []
        tasks = [str(item).strip() for item in tasks_arg if str(item).strip()] if isinstance(tasks_arg, list) else []
        if not tasks and task:
            tasks = [task]
        tasks = tasks[:8]
        if not pid or not tasks:
            return "[ERROR] projects.execute: project_id and task/tasks are required"
        try:
            project = ProjectStore(self._sub).get(pid)
        except ProjectNotFoundError:
            return f"[ERROR] projects.execute: project {pid} not found"
        if project.status != "in_progress":
            return f"[BLOCKED] projects.execute: project status is {project.status}"
        if project.policy_forbids("subagent_spawn"):
            return "[BLOCKED] projects.execute: subagent_spawn is forbidden by project policy"
        if project.policy_requires_consent("subagent_spawn"):
            ProjectStore(self._sub).set_status(
                pid,
                "waiting_choice",
                reason="subagent_spawn requires consent",
                source="project_executor",
            )
            return "[BLOCKED] projects.execute: subagent_spawn requires consent"

        run_store = ProjectRunStore(self._sub)
        trace_store = ExecutionTraceStore(self._sub)
        run = run_store.create(pid, kind="project_executor", agent_type="subagent_orchestrator")
        run_store.start(run.run_id)
        trace_store.append(
            run.run_id,
            pid,
            step_seq=0,
            step_type="task",
            content="\n".join(f"{index + 1}. {item}" for index, item in enumerate(tasks)),
            outcome="accepted",
        )

        run_steps: list[dict[str, Any]] = []
        max_retries = max(0, min(int(args.get("max_retries", 1) or 0), 3))
        requested_provider = str(args.get("provider", "")).strip()
        requested_model = str(args.get("model", "")).strip()
        for index, subtask in enumerate(tasks, start=1):
            spawned = self._spawn_project_subagent(
                pid,
                subtask,
                provider=requested_provider,
                model=requested_model,
                max_steps=int(args.get("max_steps", 6) or 6),
            )
            run_steps.append({
                "subagent_id": spawned["subagent_id"],
                "task": subtask,
                "provider": spawned["provider"],
                "model": spawned["model"],
                "status": "running" if spawned["subagent_id"] else "failed",
                "retry_count": 0,
                "max_retries": max_retries,
                "max_steps": int(args.get("max_steps", 6) or 6),
                "attempts": [spawned["subagent_id"]] if spawned["subagent_id"] else [],
                "result": "" if spawned["subagent_id"] else spawned["spawn_result"],
            })
            trace_store.append(
                run.run_id,
                pid,
                step_seq=index,
                step_type="action" if spawned["subagent_id"] else "error",
                content="spawn internal project subagent",
                tool_name="subagent.spawn",
                tool_arg_summary=subtask[:500],
                outcome=spawned["spawn_result"][:2000],
                provider=spawned["provider"],
                model=spawned["model"],
            )
        spawned_count = sum(1 for step in run_steps if step["subagent_id"])
        if not spawned_count:
            error = "\n".join(step["result"] for step in run_steps)
            run_store.update(run.run_id, steps=run_steps)
            run_store.complete(run.run_id, error=error)
            return error

        run_store.update(
            run.run_id,
            steps=run_steps,
            summary=f"Project executor spawned {spawned_count}/{len(run_steps)} subagents",
        )
        ProjectStore(self._sub).touch(pid)
        return (
            f"[OK] project execution started\n"
            f"run_id: {run.run_id}\n"
            f"subagents: {spawned_count}/{len(run_steps)}\n"
            + "\n".join(f"subagent_id: {step['subagent_id']}" for step in run_steps if step["subagent_id"])
        )

    def _harvest_project(self, args: dict) -> str:
        from sonya.memory.tool_experience import ToolExperience
        from sonya.project import ExecutionTraceStore, ProjectRunStore, ProjectStore
        from sonya.project.model import ProjectNotFoundError

        pid = str(args.get("project_id", "")).strip()
        if not pid:
            return "[ERROR] projects.harvest: project_id is required"
        try:
            ProjectStore(self._sub).get(pid)
        except ProjectNotFoundError:
            return f"[ERROR] projects.harvest: project {pid} not found"
        run_store = ProjectRunStore(self._sub)
        trace_store = ExecutionTraceStore(self._sub)
        completed = 0
        failed = 0
        pending = 0
        for run in run_store.list_by_project(pid, kind="project_executor", limit=50):
            if run.status not in ("pending", "running"):
                continue
            changed = False
            for step in run.steps:
                if not isinstance(step, dict) or step.get("status") in ("done", "failed"):
                    continue
                subagent_id = str(step.get("subagent_id", ""))
                row = self._sub.connection.execute(
                    "SELECT status, result, provider, model FROM subagent_tasks WHERE subagent_id = ?",
                    (subagent_id,),
                ).fetchone() if subagent_id else None
                if row is None:
                    row = ("failed", f"subagent {subagent_id or '(missing id)'} missing", "", "")
                status, result, provider, model = row
                if status not in ("done", "failed"):
                    continue
                if status == "failed" and int(step.get("retry_count", 0)) < int(step.get("max_retries", 0)):
                    spawned = self._spawn_project_subagent(
                        pid,
                        str(step.get("task", "")),
                        provider=str(step.get("provider", "")),
                        model=str(step.get("model", "")),
                        max_steps=int(step.get("max_steps", 6) or 6),
                    )
                    if spawned["subagent_id"]:
                        step["retry_count"] = int(step.get("retry_count", 0)) + 1
                        step["subagent_id"] = spawned["subagent_id"]
                        step.setdefault("attempts", []).append(spawned["subagent_id"])
                        step["status"] = "running"
                        self._append_run_trace(
                            trace_store, run.run_id, pid, "checkpoint",
                            f"retry {step['retry_count']} for {step.get('task', '')}",
                            tool_name="subagent.spawn", outcome=spawned["spawn_result"],
                            provider=spawned["provider"], model=spawned["model"],
                        )
                        changed = True
                        continue
                step["status"] = status
                step["result"] = result or ""
                self._append_run_trace(
                    trace_store, run.run_id, pid, "outcome", result or "",
                    tool_name="subagent.result", tool_arg_summary=subagent_id,
                    outcome="done" if status == "done" else "failed",
                    provider=provider or "", model=model or "",
                )
                ToolExperience(self._sub).record(
                    tool_name="projects.execute",
                    tool_arg_summary=subagent_id,
                    outcome="success" if status == "done" else "error",
                    outcome_detail=(result or "")[:1000],
                    provider=provider or "",
                    model=model or "",
                    session_type="project",
                )
                changed = True
            if changed:
                run_store.update(run.run_id, steps=run.steps)
            statuses = [str(step.get("status", "")) for step in run.steps if isinstance(step, dict)]
            pending_count = sum(1 for status in statuses if status not in ("done", "failed"))
            if pending_count:
                pending += pending_count
                if not changed:
                    self._append_run_trace(
                        trace_store, run.run_id, pid, "checkpoint",
                        f"progress: done={statuses.count('done')}, failed={statuses.count('failed')}, pending={pending_count}",
                        outcome="running",
                    )
                continue
            results = [str(step.get("result", "")) for step in run.steps if isinstance(step, dict)]
            failed_steps = sum(1 for status in statuses if status == "failed")
            if failed_steps:
                run_store.complete(run.run_id, error="\n\n".join(results))
                failed += 1
            else:
                run_store.complete(run.run_id, result="\n\n".join(results))
                completed += 1
        if completed or failed:
            ProjectStore(self._sub).touch(pid)
        return f"[OK] project harvest: completed={completed}, failed={failed}, pending={pending}"

    def _spawn_project_subagent(
        self,
        project_id: str,
        task: str,
        *,
        provider: str = "",
        model: str = "",
        max_steps: int = 6,
    ) -> dict[str, str]:
        from sonya.tools.subagent_tool import SubagentTool

        spawn_result = SubagentTool(
            self._sub,
            provider=self._subagent_provider,
            workspace_id=project_id,
        ).spawn(json.dumps({
            "task": task,
            "provider": provider,
            "model": model,
            "max_steps": max_steps,
        }, ensure_ascii=False))
        subagent_id = _extract_subagent_id(spawn_result)
        row = self._sub.connection.execute(
            "SELECT provider, model FROM subagent_tasks WHERE subagent_id = ?",
            (subagent_id,),
        ).fetchone() if subagent_id else None
        return {
            "subagent_id": subagent_id,
            "spawn_result": spawn_result,
            "provider": row[0] if row else "",
            "model": row[1] if row else "",
        }

    @staticmethod
    def _append_run_trace(
        trace_store,
        run_id: str,
        project_id: str,
        step_type: str,
        content: str,
        *,
        tool_name: str = "",
        tool_arg_summary: str = "",
        outcome: str = "",
        provider: str = "",
        model: str = "",
    ) -> None:
        traces = trace_store.list_by_run(run_id, limit=200)
        step_seq = (max(trace.step_seq for trace in traces) + 1) if traces else 0
        trace_store.append(
            run_id,
            project_id,
            step_seq=step_seq,
            step_type=step_type,
            content=content,
            tool_name=tool_name,
            tool_arg_summary=tool_arg_summary,
            outcome=outcome,
            provider=provider,
            model=model,
        )

    def _pressure(self, args: dict) -> str:
        action = args.get("action", "list")
        conn = self._sub.connection
        if action == "list":
            rows = conn.execute(
                "SELECT pressure_id, dimension, current_score, target_score, "
                "gap, evidence, last_evaluated_at FROM evolution_pressure "
                "ORDER BY gap DESC"
            ).fetchall()
            if not rows:
                return "Нет записей evolution pressure."
            lines = []
            for pid, dim, cur, tgt, gap, ev, le in rows:
                bar_len = int(gap * 20)
                bar = "█" * bar_len + "░" * (20 - bar_len)
                lines.append(
                    f"{dim:12s} [{bar}] {cur:.2f}→{tgt:.2f} gap={gap:.2f}"
                )
                if ev:
                    lines.append(f"             evidence: {ev[:120]}")
            return "\n".join(lines)
        if action == "update":
            dim = args.get("dimension", "")
            if not dim:
                return "Ошибка: dimension обязательно для update."
            from datetime import datetime, timezone
            import uuid
            now = datetime.now(timezone.utc).isoformat()
            cur_score = float(args.get("current_score", 0.5))
            tgt_score = float(args.get("target_score", 1.0))
            gap = max(0.0, tgt_score - cur_score)
            evidence = args.get("evidence", "")
            existing = conn.execute(
                "SELECT pressure_id FROM evolution_pressure WHERE dimension = ?",
                (dim,),
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE evolution_pressure SET current_score=?, target_score=?, "
                    "gap=?, evidence=?, last_evaluated_at=?, updated_at=? "
                    "WHERE dimension=?",
                    (cur_score, tgt_score, gap, evidence, now, now, dim),
                )
            else:
                conn.execute(
                    "INSERT INTO evolution_pressure "
                    "(pressure_id, dimension, current_score, target_score, "
                    "gap, evidence, last_evaluated_at, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (f"evo-{uuid.uuid4().hex[:8]}", dim, cur_score, tgt_score,
                     gap, evidence, now, now, now),
                )
            conn.commit()
            return f"Pressure {dim}: {cur_score:.2f}→{tgt_score:.2f} (gap={gap:.2f})"
        return f"Unknown action: {action}"


def _extract_subagent_id(text: str) -> str:
    match = re.search(r"\bsa-[0-9a-f]{12}\b", text or "")
    return match.group(0) if match else ""
