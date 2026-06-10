from __future__ import annotations

import asyncio

import pytest

from sonya.project import ExecutionTraceStore, ProjectRunStore, ProjectStore
from sonya.state.substrate import Substrate
from sonya.tools.projects_tool import ProjectsTool


class _FastProvider:
    async def complete_text(self, messages, **kwargs):
        return "[DONE] project executor result"


class _FailThenSucceedProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def complete_text(self, messages, **kwargs):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("transient provider failure")
        return "[DONE] recovered result"


class _BlockingProvider:
    async def complete_text(self, messages, **kwargs):
        await asyncio.sleep(30)
        return "[DONE] should have been cancelled"


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
