"""SubagentTool — Sonya spawns subagents from any provider/model.

Tools:
- subagent.spawn [task] — spawn a new subagent, returns subagent_id
- subagent.list — list all subagents (pending, running, done, failed)
- subagent.result [id] — get the result of a specific subagent
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from uuid import uuid4

from sonya.state.substrate import Substrate
from sonya.subject.subagent_runner import SubagentTask, SubagentRunner
from sonya.providers.llm_provider import LLMProvider
from sonya.providers.keystore import KeyStore
from sonya.tools.subagent_model_picker import PickPolicy, infer_role, is_text_loop_model, pick_subagent_model

_log = logging.getLogger("sonya.subagent")


class SubagentTool:
    """Manages subagent lifecycle: spawn, list, check results."""

    def __init__(self, substrate: Substrate, provider: LLMProvider | None = None, workspace_id: str = ""):
        self._sub = substrate
        self._provider = provider or LLMProvider(KeyStore(substrate))
        self._workspace_id = workspace_id
        self._running: dict[str, asyncio.Task] = {}
        self._already_polled: set[str] = set()

    def spawn(self, arg: str) -> str:
        """Spawn a subagent from a JSON task description.

        JSON format::
            {"task": "...", "provider?": "fireworks|kr|openrouter",
             "model?": "model/name", "max_steps?": 8}

        Returns subagent_id. The subagent runs in the background.
        Use subagent.result to check when complete.
        """
        try:
            data = json.loads(arg or "{}")
        except json.JSONDecodeError:
            # Try as plain text task
            data = {"task": arg}

        task_text = str(data.get("task", "")).strip()
        if not task_text:
            return "[ERROR] subagent.spawn: task is required"

        provider = str(data.get("provider", "")).strip()
        model = str(data.get("model", "")).strip()
        role = infer_role(task_text)
        policy = PickPolicy(
            role=role,
            prefer_free=role in ("executor", "cleanup", "transcribe", "vision", "auto"),
            prefer_low_latency=role in ("executor", "cleanup", "transcribe", "vision", "auto"),
            allow_premium=True,
        )
        pick = pick_subagent_model(
            task_text,
            KeyStore(self._sub),
            requested_provider=provider,
            requested_model=model,
            substrate=self._sub,
            policy=policy,
        )
        provider = pick.provider
        model = pick.model
        if model and not is_text_loop_model(model, provider):
            return (
                "[ERROR] subagent.spawn only supports text-loop models; "
                f"{provider}/{model} requires a special worker"
            )
        max_steps = min(int(data.get("max_steps", 6) or 6), 12)

        task = SubagentTask(
            subagent_id=f"sa-{uuid4().hex[:12]}",
            workspace_id=self._workspace_id,
            task=task_text,
            provider=provider,
            model=model,
            max_steps=max_steps,
            status="pending",
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        # Store in substrate
        self._sub.connection.execute(
            """INSERT INTO subagent_tasks
               (subagent_id, workspace_id, task, provider, model, max_steps, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)""",
            (task.subagent_id, task.workspace_id, task.task, task.provider, task.model, task.max_steps, task.created_at),
        )
        self._sub.connection.commit()

        # Launch background task
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            self._sub.connection.execute("DELETE FROM subagent_tasks WHERE subagent_id = ?", (task.subagent_id,))
            self._sub.connection.commit()
            return "[ERROR] subagent.spawn requires a running event loop"
        runner = SubagentRunner(self._sub, self._provider)
        t = loop.create_task(runner.run(task))
        self._running[task.subagent_id] = t

        return (
            f"[OK] Subagent spawned: {task.subagent_id}\n"
            f"  task: {task_text[:100]}...\n"
            f"  role: {role}\n"
            f"  provider: {task.provider}\n"
            f"  model: {task.model or '(provider default)'}\n"
            f"  selection: {pick.reason}\n"
            f"  max_steps: {task.max_steps}\n"
            f"  Check result with: subagent.result {task.subagent_id}"
        )

    def list_all(self, _arg: str = "") -> str:
        """List all subagent tasks with status."""
        rows = self._sub.connection.execute(
            """SELECT subagent_id, task, provider, model, status, steps_taken, max_steps,
                      substr(result, 1, 200), created_at, completed_at
               FROM subagent_tasks ORDER BY created_at DESC LIMIT 20"""
        ).fetchall()

        if not rows:
            return "[OK] No subagent tasks yet. Use subagent.spawn to create one."

        lines = [f"{'ID':<20s} {'STATUS':<10s} {'STEPS':<8s} {'PROVIDER':<12s} {'TASK'}" ]
        lines.append("-" * 80)
        for r in rows:
            sid = r[0][:18]
            status = r[4]
            steps = f"{r[5] or 0}/{r[6]}"
            provider = r[2][:10]
            task = (r[1] or "")[:40]
            lines.append(f"{sid:<20s} {status:<10s} {steps:<8s} {provider:<12s} {task}")
            if r[7]:
                lines.append(f"  → {r[7][:100]}")
        return "\n".join(lines)

    def result(self, arg: str) -> str:
        """Get the result of a specific subagent by ID."""
        subagent_id = (arg or "").strip()
        if not subagent_id:
            return "[ERROR] subagent.result: provide subagent_id"

        row = self._sub.connection.execute(
            """SELECT subagent_id, task, status, result, steps_taken, provider, model,
                      created_at, completed_at
               FROM subagent_tasks WHERE subagent_id = ?""",
            (subagent_id,),
        ).fetchone()

        if not row:
            return f"[ERROR] No subagent found with id: {subagent_id}"

        return (
            f"ID: {row[0]}\n"
            f"Status: {row[2]}\n"
            f"Task: {row[1][:200]}\n"
            f"Provider: {row[5]} / Model: {row[6] or 'default'}\n"
            f"Steps: {row[4]}\n"
            f"Created: {row[7]}\n"
            f"Completed: {row[8] or 'in progress'}\n"
            f"---\n"
            f"{row[3] or '(no result yet)'}"
        )

    def poll_completed(self) -> list[tuple[str, str, str]]:
        """Poll for newly completed subagent tasks.

        Called by the main loop in _tick_maintenance. Returns list of
        (subagent_id, status, result_preview) tuples for newly completed tasks.
        Only returns tasks not previously polled to avoid re-emitting.
        """
        rows = self._sub.connection.execute(
            """SELECT subagent_id, status, substr(result, 1, 300)
               FROM subagent_tasks
               WHERE status IN ('done', 'failed')
               ORDER BY completed_at DESC LIMIT 20"""
        ).fetchall()
        new_results = []
        for r in rows:
            if r[0] not in self._already_polled:
                self._already_polled.add(r[0])
                new_results.append((r[0], r[1], r[2] or ""))
        return new_results
