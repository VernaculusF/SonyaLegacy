from __future__ import annotations

import asyncio
import json

import pytest

from sonya.project import ExecutionTraceStore, ProjectRunStore, ProjectStore
from sonya.state.substrate import Substrate
from sonya.tools.projects_tool import ProjectsTool


class _FastProvider:
    async def stream_text(self, *args, **kwargs):
        yield await self.complete_text(*args, **kwargs)

    async def complete_text(self, messages, **kwargs):
        return "[DONE] project executor result"


class _FailThenSucceedProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def stream_text(self, *args, **kwargs):
        yield await self.complete_text(*args, **kwargs)

    async def complete_text(self, messages, **kwargs):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("transient provider failure")
        return "[DONE] recovered result"


class _BlockingProvider:
    async def stream_text(self, *args, **kwargs):
        yield await self.complete_text(*args, **kwargs)

    async def complete_text(self, messages, **kwargs):
        await asyncio.sleep(30)
        return "[DONE] should have been cancelled"


class _PlanningProvider:
    def __init__(self) -> None:
        self.purposes: list[str] = []

    async def stream_text(self, *args, **kwargs):
        yield await self.complete_text(*args, **kwargs)

    async def complete_text(self, messages, **kwargs):
        purpose = str(kwargs.get("purpose", ""))
        self.purposes.append(purpose)
        if purpose == "project_planner":
            return json.dumps({
                "summary": "Inspect before implementation",
                "steps": [
                    {"id": "inspect", "task": "inspect current state", "depends_on": []},
                    {"id": "implement", "task": "implement the change", "depends_on": ["inspect"]},
                ],
            })
        if purpose == "project_synthesis":
            return "Synthesized project result"
        return "[DONE] worker result"


class _WorkspaceReadingProvider:
    async def stream_text(self, *args, **kwargs):
        yield await self.complete_text(*args, **kwargs)

    async def complete_text(self, messages, **kwargs):
        if any("[OBS: filesystem.read]" in str(message.get("content", "")) for message in messages):
            observation = next(
                str(message["content"])
                for message in reversed(messages)
                if "[OBS: filesystem.read]" in str(message.get("content", ""))
            )
            return f"[DONE] {observation}"
        return "[TOOL: filesystem.read] marker.txt"


@pytest.mark.asyncio
async def test_project_execute_auto_plan_schedules_dependencies_and_synthesizes(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "project-planned-executor.db")
    try:
        project = ProjectStore(sub).create(
            "Planned executor proof",
            workspace_path=str(tmp_path),
            policy={"subagent_spawn": "allowed"},
        )
        provider = _PlanningProvider()
        tool = ProjectsTool(sub, subagent_provider=provider)

        started = await tool.execute({
            "name": "projects.execute",
            "arguments": {
                "project_id": project.project_id,
                "task": "deliver the requested change",
                "auto_plan": True,
                "max_retries": 0,
            },
        })
        assert "subagents: 1/2" in started

        run = ProjectRunStore(sub).list_by_project(project.project_id, kind="project_executor", limit=1)[0]
        assert [step["step_id"] for step in run.steps] == ["inspect", "implement"]
        assert run.steps[0]["status"] == "running"
        assert run.steps[1]["status"] == "blocked"
        assert run.steps[1]["depends_on"] == ["inspect"]
        traces = ExecutionTraceStore(sub).list_by_run(run.run_id)
        assert traces[1].step_type == "plan"
        assert '"depends_on": ["inspect"]' in traces[1].content

        await asyncio.sleep(0.05)
        first_harvest = await tool.execute({
            "name": "projects.harvest",
            "arguments": {"project_id": project.project_id},
        })
        assert "pending=1" in first_harvest
        run = ProjectRunStore(sub).get(run.run_id)
        assert run.steps[0]["status"] == "done"
        assert run.steps[1]["status"] == "running"

        await asyncio.sleep(0.05)
        second_harvest = await tool.execute({
            "name": "projects.harvest",
            "arguments": {"project_id": project.project_id},
        })
        assert "completed=1" in second_harvest
        run = ProjectRunStore(sub).get(run.run_id)
        assert run.status == "completed"
        assert run.result == "Synthesized project result"
        assert provider.purposes.count("project_planner") == 1
        assert provider.purposes.count("project_synthesis") == 1
    finally:
        sub.close()


@pytest.mark.asyncio
async def test_project_pause_stops_orchestration_until_resume(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "project-paused-executor.db")
    try:
        project = ProjectStore(sub).create(
            "Paused executor proof",
            workspace_path=str(tmp_path),
            policy={"subagent_spawn": "allowed"},
        )
        tool = ProjectsTool(sub, subagent_provider=_PlanningProvider())
        await tool.execute({
            "name": "projects.execute",
            "arguments": {
                "project_id": project.project_id,
                "task": "deliver the requested change",
                "auto_plan": True,
                "max_retries": 0,
            },
        })
        run = ProjectRunStore(sub).list_by_project(project.project_id, kind="project_executor", limit=1)[0]

        paused = await tool.execute({
            "name": "projects.pause",
            "arguments": {"project_id": project.project_id, "run_id": run.run_id},
        })
        assert "[OK]" in paused
        assert ProjectRunStore(sub).get(run.run_id).status == "paused"

        await asyncio.sleep(0.05)
        await tool.execute({
            "name": "projects.harvest",
            "arguments": {"project_id": project.project_id},
        })
        paused_run = ProjectRunStore(sub).get(run.run_id)
        assert paused_run.steps[0]["status"] == "running"
        assert paused_run.steps[1]["status"] == "blocked"

        resumed = await tool.execute({
            "name": "projects.resume",
            "arguments": {"project_id": project.project_id, "run_id": run.run_id},
        })
        assert "[OK]" in resumed
        await tool.execute({
            "name": "projects.harvest",
            "arguments": {"project_id": project.project_id},
        })
        resumed_run = ProjectRunStore(sub).get(run.run_id)
        assert resumed_run.status == "running"
        assert resumed_run.steps[0]["status"] == "done"
        assert resumed_run.steps[1]["status"] == "running"
    finally:
        sub.close()


@pytest.mark.asyncio
async def test_project_approval_request_blocks_until_explicit_decision(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "project-approval-executor.db")
    try:
        project = ProjectStore(sub).create("Approval executor proof")
        run_store = ProjectRunStore(sub)
        run = run_store.create(project.project_id, kind="project_executor")
        run_store.start(run.run_id)
        tool = ProjectsTool(sub)

        requested = await tool.execute({
            "name": "projects.request_approval",
            "arguments": {
                "project_id": project.project_id,
                "run_id": run.run_id,
                "question": "Apply the production migration?",
            },
        })
        assert "[OK]" in requested
        waiting = run_store.get(run.run_id)
        assert waiting.status == "waiting_approval"
        assert waiting.steps[-1]["kind"] == "approval"
        assert waiting.steps[-1]["decision"] == ""

        decided = await tool.execute({
            "name": "projects.decide",
            "arguments": {
                "project_id": project.project_id,
                "run_id": run.run_id,
                "decision": "deny",
            },
        })
        assert "[OK]" in decided
        denied = run_store.get(run.run_id)
        assert denied.status == "paused"
        assert denied.steps[-1]["decision"] == "deny"
    finally:
        sub.close()


@pytest.mark.asyncio
async def test_project_execute_spawns_subagent_and_harvests_result(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "project-executor.db")
    try:
        project = ProjectStore(sub).create(
            "Executor proof",
            workspace_path=str(tmp_path),
            policy={"subagent_spawn": "allowed"},
        )
        tool = ProjectsTool(sub, subagent_provider=_FastProvider())

        started = await tool.execute({
            "name": "projects.execute",
            "arguments": {
                "project_id": project.project_id,
                "task": "inspect project state",
                "max_steps": 2,
            },
        })
        assert "[OK]" in started
        assert "run-" in started
        assert "sa-" in started

        await asyncio.sleep(0.05)
        harvested = await tool.execute({
            "name": "projects.harvest",
            "arguments": {"project_id": project.project_id},
        })
        assert "completed=1" in harvested

        run = ProjectRunStore(sub).list_by_project(
            project.project_id,
            kind="project_executor",
            limit=1,
        )[0]
        assert run.status == "completed"
        assert "project executor result" in run.result
        assert run.steps[0]["subagent_id"].startswith("sa-")

        traces = ExecutionTraceStore(sub).list_by_run(run.run_id)
        assert [t.step_type for t in traces] == ["task", "action", "outcome"]
        assert traces[1].tool_name == "subagent.spawn"
        assert traces[2].outcome == "done"
    finally:
        sub.close()


@pytest.mark.asyncio
async def test_project_subagent_can_read_its_local_workspace(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "project-workspace-read.db")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "marker.txt").write_text("workspace-specific-content", encoding="utf-8")
    try:
        project = ProjectStore(sub).create(
            "Workspace read proof",
            workspace_path=str(workspace),
            policy={"subagent_spawn": "allowed"},
        )
        tool = ProjectsTool(sub, subagent_provider=_WorkspaceReadingProvider())

        started = await tool.execute({
            "name": "projects.execute",
            "arguments": {"project_id": project.project_id, "task": "read marker"},
        })
        assert "[OK]" in started
        await asyncio.sleep(0.05)
        await tool.execute({
            "name": "projects.harvest",
            "arguments": {"project_id": project.project_id},
        })

        run = ProjectRunStore(sub).list_by_project(project.project_id, kind="project_executor", limit=1)[0]
        assert run.status == "completed"
        assert "workspace-specific-content" in run.result
    finally:
        sub.close()


@pytest.mark.asyncio
async def test_project_execute_runs_multiple_independent_subagents(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "project-multi-executor.db")
    try:
        project = ProjectStore(sub).create(
            "Multi executor proof",
            workspace_path=str(tmp_path),
            policy={"subagent_spawn": "allowed"},
        )
        tool = ProjectsTool(sub, subagent_provider=_FastProvider())

        started = await tool.execute({
            "name": "projects.execute",
            "arguments": {
                "project_id": project.project_id,
                "tasks": ["inspect provider state", "inspect project state"],
                "max_retries": 0,
            },
        })
        assert "subagents: 2/2" in started

        await asyncio.sleep(0.05)
        harvested = await tool.execute({
            "name": "projects.harvest",
            "arguments": {"project_id": project.project_id},
        })
        assert "completed=1" in harvested

        run = ProjectRunStore(sub).list_by_project(project.project_id, kind="project_executor", limit=1)[0]
        assert run.status == "completed"
        assert len(run.steps) == 2
        assert all(step["status"] == "done" for step in run.steps)
        assert run.result.count("project executor result") == 2
    finally:
        sub.close()


@pytest.mark.asyncio
async def test_project_execute_keeps_concurrent_workspaces_isolated(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "project-multi-workspace.db")
    try:
        first_dir = tmp_path / "first"
        second_dir = tmp_path / "second"
        first_dir.mkdir()
        second_dir.mkdir()
        first = ProjectStore(sub).create(
            "First workspace",
            workspace_path=str(first_dir),
            policy={"subagent_spawn": "allowed"},
        )
        second = ProjectStore(sub).create(
            "Second workspace",
            workspace_path=str(second_dir),
            policy={"subagent_spawn": "allowed"},
        )
        tool = ProjectsTool(sub, subagent_provider=_FastProvider())

        first_started, second_started = await asyncio.gather(
            tool.execute({
                "name": "projects.execute",
                "arguments": {"project_id": first.project_id, "task": "inspect first"},
            }),
            tool.execute({
                "name": "projects.execute",
                "arguments": {"project_id": second.project_id, "task": "inspect second"},
            }),
        )

        assert "[OK]" in first_started
        assert "[OK]" in second_started
        rows = sub.connection.execute(
            "SELECT workspace_id, COUNT(*) FROM subagent_tasks "
            "WHERE workspace_id IN (?, ?) GROUP BY workspace_id",
            (first.project_id, second.project_id),
        ).fetchall()
        assert dict(rows) == {first.project_id: 1, second.project_id: 1}
    finally:
        sub.close()


@pytest.mark.asyncio
async def test_project_execute_blocks_inaccessible_workspace(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "project-missing-workspace.db")
    try:
        project = ProjectStore(sub).create(
            "Missing mounted workspace",
            workspace_path=str(tmp_path / "not-mounted"),
            policy={"subagent_spawn": "allowed"},
        )
        tool = ProjectsTool(sub, subagent_provider=_FastProvider())

        result = await tool.execute({
            "name": "projects.execute",
            "arguments": {"project_id": project.project_id, "task": "inspect remote files"},
        })

        assert result.startswith("[BLOCKED] projects.execute: workspace unavailable")
        assert ProjectRunStore(sub).list_by_project(project.project_id) == []
        count = sub.connection.execute(
            "SELECT COUNT(*) FROM subagent_tasks WHERE workspace_id = ?",
            (project.project_id,),
        ).fetchone()[0]
        assert count == 0
    finally:
        sub.close()


@pytest.mark.asyncio
async def test_project_harvest_retries_failed_subagent(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "project-retry-executor.db")
    try:
        project = ProjectStore(sub).create(
            "Retry executor proof",
            workspace_path=str(tmp_path),
            policy={"subagent_spawn": "allowed"},
        )
        provider = _FailThenSucceedProvider()
        tool = ProjectsTool(sub, subagent_provider=provider)

        await tool.execute({
            "name": "projects.execute",
            "arguments": {
                "project_id": project.project_id,
                "task": "retry this task",
                "max_retries": 1,
            },
        })
        await asyncio.sleep(0.05)
        first_harvest = await tool.execute({
            "name": "projects.harvest",
            "arguments": {"project_id": project.project_id},
        })
        assert "pending=1" in first_harvest

        await asyncio.sleep(0.05)
        second_harvest = await tool.execute({
            "name": "projects.harvest",
            "arguments": {"project_id": project.project_id},
        })
        assert "completed=1" in second_harvest

        run = ProjectRunStore(sub).list_by_project(project.project_id, kind="project_executor", limit=1)[0]
        assert run.status == "completed"
        assert run.steps[0]["retry_count"] == 1
        assert len(run.steps[0]["attempts"]) == 2
        assert "recovered result" in run.result
        assert "checkpoint" in [trace.step_type for trace in ExecutionTraceStore(sub).list_by_run(run.run_id)]
    finally:
        sub.close()


@pytest.mark.asyncio
async def test_project_cancel_stops_workers_across_tool_instances(tmp_path) -> None:
    sub = Substrate.open(tmp_path / "project-cancel-executor.db")
    try:
        project = ProjectStore(sub).create(
            "Cancel executor proof",
            workspace_path=str(tmp_path),
            policy={"subagent_spawn": "allowed"},
        )
        starter = ProjectsTool(sub, subagent_provider=_BlockingProvider())
        started = await starter.execute({
            "name": "projects.execute",
            "arguments": {"project_id": project.project_id, "task": "wait forever"},
        })
        assert "[OK]" in started
        run = ProjectRunStore(sub).list_by_project(project.project_id, kind="project_executor", limit=1)[0]

        canceller = ProjectsTool(sub)
        cancelled = await canceller.execute({
            "name": "projects.cancel",
            "arguments": {"project_id": project.project_id, "run_id": run.run_id},
        })
        assert "cancelled=1" in cancelled
        await asyncio.sleep(0.05)

        run = ProjectRunStore(sub).get(run.run_id)
        assert run.status == "cancelled"
        assert run.steps[0]["status"] == "cancelled"
        subagent = sub.connection.execute(
            "SELECT status, result FROM subagent_tasks WHERE subagent_id = ?",
            (run.steps[0]["subagent_id"],),
        ).fetchone()
        assert subagent == ("cancelled", "[CANCELLED] project run cancelled")
        assert ExecutionTraceStore(sub).list_by_run(run.run_id)[-1].step_type == "checkpoint"
    finally:
        sub.close()
