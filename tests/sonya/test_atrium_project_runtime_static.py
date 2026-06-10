from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_project_workspace_uses_project_runtime_api():
    workspace = (ROOT / "packages/atrium/src/components/ProjectWorkspace.jsx").read_text(
        encoding="utf-8"
    )
    store = (ROOT / "packages/atrium/src/store.js").read_text(encoding="utf-8")

    assert "fetchProjectRuns" in store
    assert "fetchProjectRuns(id)" in workspace
    assert "fetchProjectTraces(id)" in workspace
    assert "setInterval(refreshRuntime, 5000)" in workspace
    assert "Внутренние исполнители" in workspace
    assert "Ход выполнения" in workspace
