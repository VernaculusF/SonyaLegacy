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
                        "auto_plan": {
                            "type": "boolean",
                            "description": "Let Sonya decompose the task and schedule dependency-ready internal workers",
                            "default": False,
                        },
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
                "name": "projects.cancel",
                "description": (
                    "Cancel a running project executor run and its internal "
                    "workers. This is a real lifecycle cancellation, not only "
                    "a display status change."
                ),
                "parameters": {
                    "type": "object",
                    "required": ["project_id", "run_id"],
                    "properties": {
                        "project_id": {"type": "string", "description": "Project ID"},
                        "run_id": {"type": "string", "description": "Project executor run ID"},
                    },
                },
            },
            {
                "name": "projects.pause",
                "description": "Pause project orchestration. Running provider requests may finish, but no harvest, retries, dependencies, or synthesis run until resume.",
                "parameters": {
                    "type": "object",
                    "required": ["project_id", "run_id"],
                    "properties": {
                        "project_id": {"type": "string"},
                        "run_id": {"type": "string"},
                    },
                },
            },
            {
                "name": "projects.resume",
                "description": "Resume a paused project executor run from its persisted steps.",
                "parameters": {
                    "type": "object",
                    "required": ["project_id", "run_id"],
                    "properties": {
                        "project_id": {"type": "string"},
                        "run_id": {"type": "string"},
                    },
                },
            },
            {
                "name": "projects.request_approval",
                "description": "Persist an explicit project-run approval question and stop orchestration until Ivan decides.",
                "parameters": {
                    "type": "object",
                    "required": ["project_id", "run_id", "question"],
                    "properties": {
                        "project_id": {"type": "string"},
                        "run_id": {"type": "string"},
                        "question": {"type": "string"},
                    },
                },
            },
            {
                "name": "projects.decide",
                "description": "Record Ivan's explicit approve or deny decision for a waiting project run.",
                "parameters": {
                    "type": "object",
                    "required": ["project_id", "run_id", "decision"],
                    "properties": {
                        "project_id": {"type": "string"},
                        "run_id": {"type": "string"},
                        "decision": {"type": "string", "enum": ["approve", "deny"]},
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
            return await self._execute_project(args)
        if name == "projects.harvest":
            return await self._harvest_project(args)
        if name == "projects.cancel":
            return self._cancel_project(args)
        if name == "projects.pause":
            return self._control_project(args, action="pause")
        if name == "projects.resume":
            return self._control_project(args, action="resume")
        if name == "projects.request_approval":
            return self._request_project_approval(args)
        if name == "projects.decide":
            return self._decide_project(args)
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

    async def _execute_project(self, args: dict) -> str:
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
        requested_provider = str(args.get("provider", "")).strip()
        requested_model = str(args.get("model", "")).strip()
        auto_plan = bool(args.get("auto_plan")) and bool(task) and not tasks_arg
        plan_summary = ""
        raw_plan = ""
        planned_steps: list[dict[str, Any]] = []
        if auto_plan:
            raw_plan, plan_summary, planned_steps = await self._plan_project(
                task,
                provider=requested_provider,
                model=requested_model,
            )
            if raw_plan:
                trace_store.append(
                    run.run_id,
                    pid,
                    step_seq=1,
                    step_type="plan",
                    content=raw_plan,
                    outcome="accepted" if planned_steps else "fallback",
                )
        if not planned_steps:
            planned_steps = [
                {"id": f"step-{index}", "task": item, "depends_on": []}
                for index, item in enumerate(tasks, start=1)
            ]
        trace_store.append(
            run.run_id,
            pid,
            step_seq=0,
            step_type="task",
            content=task or "\n".join(f"{index + 1}. {item}" for index, item in enumerate(tasks)),
            outcome="accepted",
        )

        run_steps: list[dict[str, Any]] = []
        max_retries = max(0, min(int(args.get("max_retries", 1) or 0), 3))
        max_steps = int(args.get("max_steps", 6) or 6)
        for item in planned_steps:
            run_steps.append({
                "step_id": item["id"],
                "depends_on": item["depends_on"],
                "subagent_id": "",
                "task": item["task"],
                "root_task": task,
                "provider": requested_provider,
                "model": requested_model,
                "status": "blocked",
                "retry_count": 0,
                "max_retries": max_retries,
                "max_steps": max_steps,
                "attempts": [],
                "result": "",
                "planned": auto_plan,
            })
        self._start_ready_steps(run.run_id, pid, run_steps, trace_store)
        spawned_count = sum(1 for step in run_steps if step["subagent_id"])
        if not spawned_count:
            error = "\n".join(step["result"] for step in run_steps)
            run_store.update(run.run_id, steps=run_steps)
            run_store.complete(run.run_id, error=error)
            return error

        run_store.update(
            run.run_id,
            steps=run_steps,
            summary=plan_summary or f"Project executor spawned {spawned_count}/{len(run_steps)} subagents",
        )
        ProjectStore(self._sub).touch(pid)
        return (
            f"[OK] project execution started\n"
            f"run_id: {run.run_id}\n"
            f"subagents: {spawned_count}/{len(run_steps)}\n"
            + "\n".join(f"subagent_id: {step['subagent_id']}" for step in run_steps if step["subagent_id"])
        )

    async def _harvest_project(self, args: dict) -> str:
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
                if not isinstance(step, dict) or step.get("status") in ("done", "failed", "cancelled"):
                    continue
                if step.get("status") == "blocked":
                    continue
                subagent_id = str(step.get("subagent_id", ""))
                row = self._sub.connection.execute(
                    "SELECT status, result, provider, model FROM subagent_tasks WHERE subagent_id = ?",
                    (subagent_id,),
                ).fetchone() if subagent_id else None
                if row is None:
                    row = ("failed", f"subagent {subagent_id or '(missing id)'} missing", "", "")
                status, result, provider, model = row
                if status not in ("done", "failed", "cancelled"):
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
            terminal_by_id = {
                str(step.get("step_id", "")): str(step.get("status", ""))
                for step in run.steps if isinstance(step, dict)
            }
            for step in run.steps:
                if not isinstance(step, dict) or step.get("status") != "blocked":
                    continue
                dependency_states = [terminal_by_id.get(str(dep), "") for dep in step.get("depends_on", [])]
                if any(state in ("failed", "cancelled") for state in dependency_states):
                    step["status"] = "failed"
                    step["result"] = "[BLOCKED] dependency failed or was cancelled"
                    self._append_run_trace(
                        trace_store, run.run_id, pid, "error",
                        str(step["result"]), tool_arg_summary=str(step.get("step_id", "")),
                        outcome="failed",
                    )
                    changed = True
            if self._start_ready_steps(run.run_id, pid, run.steps, trace_store):
                changed = True
            if changed:
                run_store.update(run.run_id, steps=run.steps)
            statuses = [str(step.get("status", "")) for step in run.steps if isinstance(step, dict)]
            pending_count = sum(1 for status in statuses if status not in ("done", "failed", "cancelled"))
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
                result = "\n\n".join(results)
                if any(bool(step.get("planned")) for step in run.steps if isinstance(step, dict)):
                    result = await self._synthesize_project(run.steps) or result
                    self._append_run_trace(
                        trace_store, run.run_id, pid, "outcome", result,
                        tool_name="project.synthesis", outcome="done",
                    )
                run_store.complete(run.run_id, result=result)
                completed += 1
        if completed or failed:
            ProjectStore(self._sub).touch(pid)
        return f"[OK] project harvest: completed={completed}, failed={failed}, pending={pending}"

    def _cancel_project(self, args: dict) -> str:
        from sonya.project import ExecutionTraceStore, ProjectRunStore
        from sonya.project.model import RunNotFoundError
        from sonya.subject.subagent_lifecycle import cancel_subagent

        pid = str(args.get("project_id", "")).strip()
        run_id = str(args.get("run_id", "")).strip()
        if not pid or not run_id:
            return "[ERROR] projects.cancel: project_id and run_id are required"
        run_store = ProjectRunStore(self._sub)
        try:
            run = run_store.get(run_id)
        except RunNotFoundError:
            return f"[ERROR] projects.cancel: run {run_id} not found"
        if run.project_id != pid:
            return f"[ERROR] projects.cancel: run {run_id} does not belong to project {pid}"
        if run.status not in ("pending", "running"):
            return f"[OK] project run already terminal: {run.status}"

        cancelled = 0
        for step in run.steps:
            if not isinstance(step, dict) or step.get("status") in ("done", "failed", "cancelled"):
                continue
            if cancel_subagent(
                self._sub,
                str(step.get("subagent_id", "")),
                reason="project run cancelled",
            ):
                cancelled += 1
            step["status"] = "cancelled"
            step["result"] = "[CANCELLED] project run cancelled"
        run_store.update(run_id, status="cancelled", steps=run.steps, error="[CANCELLED] project run cancelled")
        self._append_run_trace(
            ExecutionTraceStore(self._sub),
            run_id,
            pid,
            "checkpoint",
            f"project run cancelled; workers={cancelled}",
            outcome="cancelled",
        )
        return f"[OK] project run cancelled: cancelled={cancelled}"

    def _control_project(self, args: dict, *, action: str) -> str:
        from sonya.project import ExecutionTraceStore, ProjectRunStore
        from sonya.project.model import RunNotFoundError

        pid = str(args.get("project_id", "")).strip()
        run_id = str(args.get("run_id", "")).strip()
        if not pid or not run_id:
            return f"[ERROR] projects.{action}: project_id and run_id are required"
        store = ProjectRunStore(self._sub)
        try:
            run = store.get(run_id)
        except RunNotFoundError:
            return f"[ERROR] projects.{action}: run {run_id} not found"
        if run.project_id != pid:
            return f"[ERROR] projects.{action}: run {run_id} does not belong to project {pid}"
        if action == "pause":
            if run.status not in ("pending", "running"):
                return f"[BLOCKED] projects.pause: run status is {run.status}"
            status = "paused"
            content = "project orchestration paused; running provider requests may finish"
        else:
            if run.status != "paused":
                return f"[BLOCKED] projects.resume: run status is {run.status}"
            status = "running"
            content = "project orchestration resumed"
        store.update(run_id, status=status)
        self._append_run_trace(
            ExecutionTraceStore(self._sub),
            run_id,
            pid,
            "checkpoint",
            content,
            outcome=status,
        )
        return f"[OK] project run {status}: {run_id}"

    def _request_project_approval(self, args: dict) -> str:
        from sonya.project import ExecutionTraceStore, ProjectRunStore
        from sonya.project.model import RunNotFoundError

        pid = str(args.get("project_id", "")).strip()
        run_id = str(args.get("run_id", "")).strip()
        question = str(args.get("question", "")).strip()
        if not pid or not run_id or not question:
            return "[ERROR] projects.request_approval: project_id, run_id, and question are required"
        store = ProjectRunStore(self._sub)
        try:
            run = store.get(run_id)
        except RunNotFoundError:
            return f"[ERROR] projects.request_approval: run {run_id} not found"
        if run.project_id != pid or run.status not in ("pending", "running", "paused"):
            return f"[BLOCKED] projects.request_approval: run status is {run.status}"
        run.steps.append({
            "kind": "approval",
            "status": "waiting",
            "question": question,
            "decision": "",
        })
        store.update(run_id, status="waiting_approval", steps=run.steps)
        self._append_run_trace(
            ExecutionTraceStore(self._sub), run_id, pid, "decision",
            question, tool_name="projects.request_approval", outcome="waiting_approval",
        )
        return f"[OK] project approval requested: {run_id}"

    def _decide_project(self, args: dict) -> str:
        from sonya.project import ExecutionTraceStore, ProjectRunStore
        from sonya.project.model import RunNotFoundError

        pid = str(args.get("project_id", "")).strip()
        run_id = str(args.get("run_id", "")).strip()
        decision = str(args.get("decision", "")).strip()
        if decision not in ("approve", "deny"):
            return "[ERROR] projects.decide: decision must be approve or deny"
        store = ProjectRunStore(self._sub)
        try:
            run = store.get(run_id)
        except RunNotFoundError:
            return f"[ERROR] projects.decide: run {run_id} not found"
        if run.project_id != pid or run.status != "waiting_approval":
            return f"[BLOCKED] projects.decide: run status is {run.status}"
        approval = next(
            (step for step in reversed(run.steps) if isinstance(step, dict) and step.get("kind") == "approval" and not step.get("decision")),
            None,
        )
        if approval is None:
            return "[ERROR] projects.decide: pending approval not found"
        approval["decision"] = decision
        approval["status"] = "done"
        status = "running" if decision == "approve" else "paused"
        store.update(run_id, status=status, steps=run.steps)
        self._append_run_trace(
            ExecutionTraceStore(self._sub), run_id, pid, "decision",
            f"project approval decision: {decision}", tool_name="projects.decide", outcome=status,
        )
        return f"[OK] project approval {decision}: {run_id}"

    async def _plan_project(
        self,
        task: str,
        *,
        provider: str = "",
        model: str = "",
    ) -> tuple[str, str, list[dict[str, Any]]]:
        if self._subagent_provider is None:
            return "", "", []
        kwargs: dict[str, Any] = {"purpose": "project_planner", "role": "manager"}
        if provider:
            kwargs["_provider"] = provider
        if model:
            kwargs["_model"] = model
        try:
            raw = await self._subagent_provider.complete_text(
                [
                    {
                        "role": "system",
                        "content": (
                            "Plan internal project work for Sonya. Return only one JSON object "
                            "with summary and steps. Each step needs id, task, and depends_on. "
                            "Use at most 8 steps. Do not invent work that is not needed."
                        ),
                    },
                    {"role": "user", "content": task},
                ],
                **kwargs,
            )
        except Exception as exc:
            return f"[planner error] {exc}", "", []
        summary, steps = _parse_project_plan(raw)
        return raw, summary, steps

    async def _synthesize_project(self, steps: list[dict[str, Any]]) -> str:
        if self._subagent_provider is None:
            return ""
        first = next((step for step in steps if isinstance(step, dict)), {})
        kwargs: dict[str, Any] = {"purpose": "project_synthesis", "role": "manager"}
        if first.get("provider"):
            kwargs["_provider"] = str(first["provider"])
        if first.get("model"):
            kwargs["_model"] = str(first["model"])
        evidence = [
            {
                "step_id": step.get("step_id", ""),
                "task": step.get("task", ""),
                "result": step.get("result", ""),
            }
            for step in steps if isinstance(step, dict)
        ]
        try:
            return await self._subagent_provider.complete_text(
                [
                    {
                        "role": "system",
                        "content": (
                            "Synthesize the internal project worker outcomes into Sonya's final "
                            "project result. Preserve concrete evidence and unresolved limits."
                        ),
                    },
                    {
                        "role": "user",
                        "content": json.dumps({
                            "task": first.get("root_task", ""),
                            "worker_outcomes": evidence,
                        }, ensure_ascii=False),
                    },
                ],
                **kwargs,
            )
        except Exception:
            return ""

    def _start_ready_steps(
        self,
        run_id: str,
        project_id: str,
        steps: list[dict[str, Any]],
        trace_store: Any,
    ) -> int:
        statuses = {
            str(step.get("step_id", "")): str(step.get("status", ""))
            for step in steps if isinstance(step, dict)
        }
        started = 0
        for step in steps:
            if not isinstance(step, dict) or step.get("status") != "blocked":
                continue
            dependencies = [str(dep) for dep in step.get("depends_on", [])]
            if not all(statuses.get(dep) == "done" for dep in dependencies):
                continue
            spawned = self._spawn_project_subagent(
                project_id,
                str(step.get("task", "")),
                provider=str(step.get("provider", "")),
                model=str(step.get("model", "")),
                max_steps=int(step.get("max_steps", 6) or 6),
            )
            step["subagent_id"] = spawned["subagent_id"]
            step["provider"] = spawned["provider"]
            step["model"] = spawned["model"]
            step["status"] = "running" if spawned["subagent_id"] else "failed"
            step.setdefault("attempts", [])
            if spawned["subagent_id"]:
                step["attempts"].append(spawned["subagent_id"])
                started += 1
            else:
                step["result"] = spawned["spawn_result"]
            self._append_run_trace(
                trace_store,
                run_id,
                project_id,
                "action" if spawned["subagent_id"] else "error",
                "spawn internal project subagent",
                tool_name="subagent.spawn",
                tool_arg_summary=str(step.get("task", ""))[:500],
                outcome=spawned["spawn_result"][:2000],
                provider=spawned["provider"],
                model=spawned["model"],
            )
        return started

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


def _parse_project_plan(raw: str) -> tuple[str, list[dict[str, Any]]]:
    text = str(raw or "").strip()
    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]).strip()
    try:
        payload = json.loads(text)
    except (TypeError, ValueError):
        return "", []
    if not isinstance(payload, dict) or not isinstance(payload.get("steps"), list):
        return "", []
    parsed: list[dict[str, Any]] = []
    ids: set[str] = set()
    for item in payload["steps"][:8]:
        if not isinstance(item, dict):
            return "", []
        step_id = str(item.get("id", "")).strip()
        task = str(item.get("task", "")).strip()
        depends_on = item.get("depends_on", [])
        if not step_id or not task or step_id in ids or not isinstance(depends_on, list):
            return "", []
        ids.add(step_id)
        parsed.append({
            "id": step_id,
            "task": task,
            "depends_on": [str(dep).strip() for dep in depends_on if str(dep).strip()],
        })
    if not parsed:
        return "", []
    if any(dep not in ids or dep == item["id"] for item in parsed for dep in item["depends_on"]):
        return "", []
    resolved: set[str] = set()
    remaining = list(parsed)
    while remaining:
        ready = [item for item in remaining if all(dep in resolved for dep in item["depends_on"])]
        if not ready:
            return "", []
        for item in ready:
            resolved.add(item["id"])
            remaining.remove(item)
    return str(payload.get("summary", "")).strip(), parsed
