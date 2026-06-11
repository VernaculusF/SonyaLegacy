from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_sidebar_exposes_one_main_chat_and_only_real_project_chats() -> None:
    source = (ROOT / "packages/atrium/src/components/ChatSidebar.jsx").read_text(encoding="utf-8")

    assert "Sonya's home" in source
    assert "createProject(" in source
    assert "projPath().trim()" in source
    assert "ssh://user@host/absolute/path" in source
    assert "feed.projects" in source
    assert "createWorkspace(" not in source
    assert "removeWorkspace(" not in source
    assert "settings.workspaces" not in source


def test_legacy_projects_drawer_is_removed() -> None:
    assert not (ROOT / "packages/atrium/src/components/ProjectsDrawer.jsx").exists()
