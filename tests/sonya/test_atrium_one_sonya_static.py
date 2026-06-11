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


def test_atrium_keeps_sonya_avatar_and_dialog_present_in_every_chat() -> None:
    source = (ROOT / "packages/atrium/src/App.jsx").read_text(encoding="utf-8")

    assert "import AvatarPane" in source
    assert "<AvatarPane" in source
    assert "<DialogPane" in source
    assert "fallback={<DialogPane" not in source
    assert "when={activeWorkspaceId() !== 'main'}" in source
    assert "fallback={<MindPane" in source


def test_chat_selector_is_an_overlay_not_a_permanent_main_column() -> None:
    source = (ROOT / "packages/atrium/src/components/ChatSidebar.jsx").read_text(encoding="utf-8")
    styles = (ROOT / "packages/atrium/src/styles.css").read_text(encoding="utf-8")

    assert "props.open()" in source
    assert "chat-drawer-overlay" in source
    assert "'chat-sidebar': true, open: props.open()" in source
    assert ".chat-sidebar.open" in styles
    assert "position: fixed" in styles


def test_bundled_avatar_assets_are_atrium_base_aware() -> None:
    source = (ROOT / "packages/atrium/src/store.js").read_text(encoding="utf-8")

    assert "import.meta.env.BASE_URL" in source
    assert "atriumAsset(" in source
    assert "merged.avatar_frames.every((u) => isBundledAvatarAsset(u))" in source
    assert "avatar_model_url: '/models/sonya.vrm'" not in source
    assert "'/avatar/sonya_closed.png'" not in source
    assert "desire: '/avatar/emotions/desire.png'" not in source


def test_avatar_falls_back_to_drawn_head_when_sprite_assets_fail() -> None:
    source = (ROOT / "packages/atrium/src/components/SonyaAvatar.jsx").read_text(encoding="utf-8")

    assert "frameLoadFailed" in source
    assert "const hasFrames = () => frames().length > 0 && !frameLoadFailed()" in source
    assert "onError={onFrameError}" in source
    assert "fallback={<DrawnHead" in source


def test_dialog_loads_initial_history_and_preserves_workspace_scope() -> None:
    source = (ROOT / "packages/atrium/src/components/DialogPane.jsx").read_text(encoding="utf-8")

    assert "loadedHistoryWorkspaces" in source
    assert "if (!visibleMessages().length) loadOlderHistory()" in source
    assert "payload.workspace_id ? { workspace_id: payload.workspace_id }" in source


def test_reason_stream_has_scrollback_history_loader() -> None:
    source = (ROOT / "packages/atrium/src/components/ReasonStream.jsx").read_text(encoding="utf-8")
    ws = (ROOT / "packages/atrium/src/ws.js").read_text(encoding="utf-8")
    store = (ROOT / "packages/atrium/src/store.js").read_text(encoding="utf-8")

    assert "onMount" in source
    assert "loadOlderEvents();" in source
    assert "loadEventHistory" in source
    assert "prependStreamEvents" in source
    assert "onScroll={onScroll}" in source
    assert "/api/atrium/events-history" in ws
    assert "export function prependStreamEvents" in store
