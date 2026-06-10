from __future__ import annotations

import asyncio

import pytest

from sonya.project import ExecutionTraceStore, ProjectRunStore, ProjectStore
from sonya.state.substrate import Substrate
from sonya.tools.projects_tool import ProjectsTool


class _FastProvider:
    async def complete_text(self, messages, **kwargs):
        return "[DONE] project executor result"


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

