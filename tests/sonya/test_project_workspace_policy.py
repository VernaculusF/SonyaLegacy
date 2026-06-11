from __future__ import annotations

import asyncio
import json
from pathlib import Path

from sonya.project import ProjectStore, WorkspacePolicyStore
from sonya.state.substrate import Substrate
from sonya.tools.projects_tool import ProjectsTool


def test_projects_check_policy_reflects_workspace_full_system_access(tmp_path: Path) -> None:
    sub = Substrate.open(tmp_path / "workspace-policy.db")
    try:
        project = ProjectStore(sub).create("full access policy", workspace_path=str(tmp_path))
        tool = ProjectsTool(sub)

        before = asyncio.run(tool.execute({
            "name": "projects.check_policy",
            "arguments": {"project_id": project.project_id, "action": "shell_run"},
        }))
        assert before.startswith("CONSENT:")
        assert "source=project_policy" in before

        WorkspacePolicyStore(sub).set_full_system_access(project.project_id, True)
        after = asyncio.run(tool.execute({
            "name": "projects.check_policy",
            "arguments": {"project_id": project.project_id, "action": "shell_run"},
        }))

        assert after.startswith("ALLOWED:")
        assert "source=workspace_policy" in after
        assert "full_system_access=true" in after
    finally:
        sub.close()


def test_project_check_policy_api_exposes_workspace_policy_source(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("SONYA_SUBSTRATE_PATH", str(tmp_path / "policy-api.db"))
    from sonya.admin.project_api import api_project_check_policy
    from sonya.config import load_config

    sub = Substrate.open(tmp_path / "policy-api.db")
    try:
        project = ProjectStore(sub).create("full access api", workspace_path=str(tmp_path))
        WorkspacePolicyStore(sub).set_full_system_access(project.project_id, True)
    finally:
        sub.close()

    class _Req:
        app = {"config": load_config()}
        match_info = {"project_id": project.project_id}

        async def json(self):
            return {"action": "file_write"}

    response = asyncio.run(api_project_check_policy(_Req()))
    payload = json.loads(response.text)

    assert payload["verdict"] == "allowed"
    assert payload["source"] == "workspace_policy"
    assert payload["full_system_access"] is True
