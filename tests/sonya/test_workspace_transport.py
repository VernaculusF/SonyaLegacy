from __future__ import annotations

import json
import subprocess

import pytest

from sonya.tools.workspace_transport import SSHWorkspaceTool, parse_ssh_workspace, resolve_workspace_tools


def test_parse_ssh_workspace_rejects_embedded_secret() -> None:
    with pytest.raises(ValueError):
        parse_ssh_workspace("ssh://user:password@example.com/workspace")


def test_parse_ssh_workspace_keeps_target_port_and_root() -> None:
    workspace = parse_ssh_workspace("ssh://ivan@example.com:2222/srv/project")

    assert workspace is not None
    assert workspace.target == "ivan@example.com"
    assert workspace.port == 2222
    assert workspace.root == "/srv/project"


def test_local_workspace_tools_expose_read_search_and_code(tmp_path) -> None:
    (tmp_path / "note.txt").write_text("unique workspace marker", encoding="utf-8")

    filesystem, code, detail = resolve_workspace_tools(str(tmp_path))

    assert "unique workspace marker" in filesystem.read_file("note.txt")
    assert "note.txt:1" in filesystem.search("workspace marker")
    assert "[exit 0]" in code.exec_python("print('ok')")
    assert detail == str(tmp_path.resolve())


def test_ssh_workspace_uses_fixed_batch_command_without_raw_payload(monkeypatch) -> None:
    workspace = parse_ssh_workspace("ssh://ivan@example.com/srv/project")
    assert workspace is not None
    seen: list[list[str]] = []

    def fake_run(argv, **kwargs):
        seen.append(argv)
        return subprocess.CompletedProcess(argv, 0, stdout=b'{"ok": true}\n', stderr=b"")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert SSHWorkspaceTool(workspace).probe() is True
    command = seen[0][-1]
    assert seen[0][:5] == ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10"]
    assert seen[0][-2] == "ivan@example.com"
    assert "/srv/project" not in command
    assert json.dumps({"op": "probe", "root": "/srv/project", "path": ""}) not in command
