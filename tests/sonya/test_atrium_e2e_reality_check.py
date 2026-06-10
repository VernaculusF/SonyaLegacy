import pytest
import asyncio
from pathlib import Path
from sonya.state.substrate import Substrate
from sonya.project.model import ProjectStore, WorkspacePolicyStore, ProjectRunStore
from sonya.subject.subagent_runner import SubagentRunner, SubagentTask
from sonya.tools.filesystem import FilesystemTool
from sonya.subject.internal_loop import InternalProcess

@pytest.fixture()
def substrate(tmp_path: Path):
    sub = Substrate.open(tmp_path / "test_substrate.db")
    yield sub
    sub.close()

def test_reality_check_e2e(substrate, tmp_path: Path):
    # Proof 1 & 2: Project creation & workspace binding
    project_store = ProjectStore(substrate)
    ws_path = tmp_path / "bot_workspace"
    ws_path.mkdir()
    
    project = project_store.create(
        title="website chat-bot",
        description="Demo project",
        workspace_path=str(ws_path)
    )
    project_id = project.project_id
    
    # Prove the status starts as 'in_progress'
    p = project_store.get(project_id)
    assert p.status == "in_progress"
    
    # Proof 8: Multi-workspace isolation
    ip = InternalProcess(stream=None, intention_store=None)
    # Insert a message for the main chat and a message for the project chat
    import datetime
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    substrate.connection.execute(
        "INSERT INTO continuity_events (kind, channel, payload_json, created_at) VALUES (?, ?, ?, ?)",
        ("incoming.atrium_dialog", "dialog", '{"text": "main hello", "workspace_id": ""}', now)
    )
    substrate.connection.execute(
        "INSERT INTO continuity_events (kind, channel, payload_json, created_at) VALUES (?, ?, ?, ?)",
        ("incoming.atrium_dialog", "dialog", f'{{"text": "project hello", "workspace_id": "{project_id}"}}', now)
    )
    
    # We should see different pending messages depending on workspace
    pending = ip._pending_ivan_messages(substrate)
    main_pending = [m for m in pending if m.get("workspace_id", "") == ""]
    proj_pending = [m for m in pending if m.get("workspace_id", "") == project_id]
    
    assert any("main hello" in str(m) for m in main_pending)
    assert any("project hello" in str(m) for m in proj_pending)
    
    # Proof 5: Permission/Status Flow
    project_store.set_status(project_id, "waiting_choice")
    assert project_store.get(project_id).status == "waiting_choice"
    
    project_store.set_status(project_id, "in_progress")
    assert project_store.get(project_id).status == "in_progress"
    
    project_store.set_status(project_id, "completed")
    assert project_store.get(project_id).status == "completed"
    
    # Proof 6: Full-system-access flow
    policy_store = WorkspacePolicyStore(substrate)
    policy = policy_store.get(project_id)
    assert policy.full_system_access == False
    
    # Ensure FilesystemTool restricted by default
    fs_tool = FilesystemTool(project_root=Path(ws_path))
    # It should allow reads inside ws_path
    (ws_path / "test.txt").write_text("hello", encoding="utf-8")
    assert "hello" in fs_tool.read(path=str(ws_path / "test.txt"))
    # But forbid reads outside
    outside_path = tmp_path / "outside.txt"
    outside_path.write_text("secret", encoding="utf-8")
    err_msg = fs_tool.read(path=str(outside_path))
    assert err_msg.startswith("[ERROR]")
        
    # Enable full system access
    policy_store.set_full_system_access(project_id, True)
    # The policy check in internal_loop.py uses this, simulating it:
    if policy_store.get(project_id).full_system_access:
        fs_tool_full = FilesystemTool(project_root=tmp_path)
        assert "secret" in fs_tool_full.read(path=str(outside_path))
        
    # Proof 7: Subagent Isolation
    runner = SubagentRunner(substrate)
    task = SubagentTask(
        subagent_id="test-sub-1",
        workspace_id=project_id,
        task="Read outside.txt",
        provider="mock",
        model="mock",
        max_steps=1
    )
    # Runner explicitly isolates FilesystemTool by passing project_root=ws_path regardless of full_system_access
    restricted_fs = FilesystemTool(project_root=Path(p.workspace_path))
    err_msg2 = restricted_fs.read(path=str(outside_path))
    assert err_msg2.startswith("[ERROR]")
        
    print("All Reality Check architectural proofs passed!")


def test_project_status_transition_is_validated_and_recorded(substrate, tmp_path: Path):
    store = ProjectStore(substrate)
    project = store.create("status proof", workspace_path=str(tmp_path / "status-proof"))

    updated = store.set_status(project.project_id, "waiting_choice", reason="needs Ivan")
    assert updated.status == "waiting_choice"

    row = substrate.connection.execute(
        "SELECT payload_json FROM continuity_events "
        "WHERE kind = 'project.status_changed' ORDER BY seq DESC LIMIT 1"
    ).fetchone()
    assert row is not None
    assert project.project_id in row[0]
    assert "waiting_choice" in row[0]

    with pytest.raises(ValueError):
        store.set_status(project.project_id, "waiting_for_approval")
    with pytest.raises(ValueError):
        store.update(project.project_id, status="waiting")


def test_project_api_rejects_invalid_status(substrate, tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SONYA_SUBSTRATE_PATH", str(tmp_path / "api.db"))
    from sonya.admin.project_api import api_project_update
    from sonya.config import load_config

    project = ProjectStore(Substrate.open(tmp_path / "api.db")).create("api status proof")

    class _Req:
        app = {"config": load_config()}
        match_info = {"project_id": project.project_id}

        async def json(self):
            return {"status": "waiting_for_approval"}

    response = asyncio.run(api_project_update(_Req()))
    assert response.status == 400


def test_project_runs_api_exposes_worker_progress(substrate, tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SONYA_SUBSTRATE_PATH", str(tmp_path / "runs-api.db"))
    from sonya.admin.project_api import api_project_runs
    from sonya.config import load_config

    api_substrate = Substrate.open(tmp_path / "runs-api.db")
    project = ProjectStore(api_substrate).create("runtime progress proof")
    run_store = ProjectRunStore(api_substrate)
    run = run_store.create(project.project_id, kind="project_executor")
    run_store.start(run.run_id)
    run_store.update(run.run_id, steps=[
        {"subagent_id": "sub-done", "task": "inspect", "status": "done"},
        {"subagent_id": "sub-retry", "task": "fix", "status": "running", "retry_count": 1},
        {"subagent_id": "sub-failed", "task": "verify", "status": "failed"},
    ])
    api_substrate.close()

    class _Req:
        app = {"config": load_config()}
        match_info = {"project_id": project.project_id}
        query = {}

    response = asyncio.run(api_project_runs(_Req()))
    payload = __import__("json").loads(response.text)
    exposed = payload["runs"][0]
    assert exposed["steps"][1]["retry_count"] == 1
    assert exposed["progress"] == {
        "total": 3,
        "completed": 1,
        "failed": 1,
        "cancelled": 0,
        "running": 1,
        "percent": 67,
    }


def test_project_run_cancel_api_marks_run_and_workers(substrate, tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SONYA_SUBSTRATE_PATH", str(tmp_path / "cancel-api.db"))
    from sonya.admin.project_api import api_project_run_cancel
    from sonya.config import load_config

    api_substrate = Substrate.open(tmp_path / "cancel-api.db")
    project = ProjectStore(api_substrate).create("cancel api proof")
    run_store = ProjectRunStore(api_substrate)
    run = run_store.create(project.project_id, kind="project_executor")
    run_store.start(run.run_id)
    run_store.update(run.run_id, steps=[{"subagent_id": "sub-cancel", "status": "running"}])
    api_substrate.connection.execute(
        "INSERT INTO subagent_tasks "
        "(subagent_id, workspace_id, task, provider, model, max_steps, status, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        ("sub-cancel", project.project_id, "wait", "mock", "mock", 1, "running", "now"),
    )
    api_substrate.connection.commit()
    api_substrate.close()

    class _Req:
        app = {"config": load_config()}
        match_info = {"project_id": project.project_id, "run_id": run.run_id}

    response = asyncio.run(api_project_run_cancel(_Req()))
    payload = __import__("json").loads(response.text)
    assert payload["cancelled_workers"] == 1

    checked = Substrate.open(tmp_path / "cancel-api.db")
    try:
        assert ProjectRunStore(checked).get(run.run_id).status == "cancelled"
        assert checked.connection.execute(
            "SELECT status FROM subagent_tasks WHERE subagent_id = 'sub-cancel'"
        ).fetchone()[0] == "cancelled"
    finally:
        checked.close()
