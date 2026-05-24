"""Tests for FilesystemTool — focused on the path-mangling bugs that produced
``workspace/earnings_blackhat.md\\n#`` literal filenames on the VPS.

Root cause: the agent_session dispatcher used ``arg.split(" ", 1)`` for
``filesystem.write``, which on multi-line content like ``path\\n# header``
returns ``["path\\n#", "header"]``. The fix splits on newline first, with
space-split as inline fallback. Filesystem.write itself also rejects paths
with control chars as defense in depth.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from sonya.tools.filesystem import FilesystemTool


@pytest.fixture
def fs(tmp_path: Path) -> FilesystemTool:
    return FilesystemTool(project_root=tmp_path)


def test_write_normal_path(fs: FilesystemTool, tmp_path: Path) -> None:
    result = fs.write("workspace/notes.md", "# Hello\nworld\n")
    assert result.startswith("[OK]")
    assert (tmp_path / "workspace" / "notes.md").read_text(encoding="utf-8") == "# Hello\nworld\n"


def test_write_rejects_newline_in_path(fs: FilesystemTool, tmp_path: Path) -> None:
    """The wineandmore-night-of-23.05 bug: path arg = 'workspace/foo.md\\n#'."""
    result = fs.write("workspace/foo.md\n#", "content")
    assert result.startswith("[ERROR]")
    assert "newline" in result
    assert not (tmp_path / "workspace").exists()


def test_write_rejects_carriage_return_in_path(fs: FilesystemTool) -> None:
    # \r in the middle of a path (e.g. CRLF line endings before parser ran)
    result = fs.write("workspace/foo.md\rextra", "content")
    assert result.startswith("[ERROR]")


def test_write_rejects_null_in_path(fs: FilesystemTool) -> None:
    result = fs.write("workspace/foo.md\0evil", "content")
    assert result.startswith("[ERROR]")


def test_write_rejects_empty_path(fs: FilesystemTool) -> None:
    assert fs.write("", "content").startswith("[ERROR]")
    assert fs.write("   ", "content").startswith("[ERROR]")


def test_write_strips_path_whitespace(fs: FilesystemTool, tmp_path: Path) -> None:
    """Block-form parser may leave trailing whitespace in the path line."""
    result = fs.write("  workspace/notes.md  ", "x")
    assert result.startswith("[OK]")
    assert (tmp_path / "workspace" / "notes.md").read_text(encoding="utf-8") == "x"


def test_write_rejects_quote_in_path(fs: FilesystemTool) -> None:
    """The {"path": ... bug: model passed JSON literal as filename."""
    result = fs.write('{"path":"workspace/foo.md","content":"x"}', "stuff")
    assert result.startswith("[ERROR]")


def test_write_allows_multiline_content(fs: FilesystemTool, tmp_path: Path) -> None:
    """Path is fine, content can have any characters including newlines."""
    big = "# Title\n\nLine one\nLine two\n```python\nprint(1)\n```\n"
    result = fs.write("workspace/notes.md", big)
    assert result.startswith("[OK]")
    assert (tmp_path / "workspace" / "notes.md").read_text(encoding="utf-8") == big


def test_write_to_subdirectory_creates_parents(fs: FilesystemTool, tmp_path: Path) -> None:
    result = fs.write("workspace/deep/nested/notes.md", "x")
    assert result.startswith("[OK]")
    assert (tmp_path / "workspace" / "deep" / "nested" / "notes.md").exists()


# --- agent_session dispatch tests ---


def test_dispatch_block_form_splits_on_newline(tmp_path: Path) -> None:
    """Block form: first line = path, remaining = content. Without this fix
    (split on space), 'path\\n# title' yielded path='path\\n#'.
    """
    from sonya.subject.agent_session import _execute_tool
    from sonya.tools.self_inspect import SelfInspectTool
    from sonya.state.substrate import Substrate
    from sonya.state import seed_identity_if_empty

    sub = Substrate.open(tmp_path / "test.db")
    seed_identity_if_empty(sub)
    try:
        si = SelfInspectTool(sub)
        fs = FilesystemTool(project_root=tmp_path)

        # Block form arg as the parser sees it after fence stripping:
        # "workspace/notes.md\n# Поиск способов\n...content..."
        block_arg = "workspace/notes.md\n# Поиск способов\nLine 2\n"
        result = _execute_tool("filesystem.write", block_arg, si, fs)
        assert result.startswith("[OK]"), f"got: {result}"
        # File exists with the SANE name (no \n#)
        assert (tmp_path / "workspace" / "notes.md").exists()
        # And the content does NOT include the path on first line
        body = (tmp_path / "workspace" / "notes.md").read_text(encoding="utf-8")
        assert body.startswith("# Поиск способов")
    finally:
        sub.close()


def test_dispatch_inline_form_split_on_space(tmp_path: Path) -> None:
    """Inline form (no newlines): first space-separated token = path, rest = content."""
    from sonya.subject.agent_session import _execute_tool
    from sonya.tools.self_inspect import SelfInspectTool
    from sonya.state.substrate import Substrate
    from sonya.state import seed_identity_if_empty

    sub = Substrate.open(tmp_path / "test.db")
    seed_identity_if_empty(sub)
    try:
        si = SelfInspectTool(sub)
        fs = FilesystemTool(project_root=tmp_path)

        result = _execute_tool(
            "filesystem.write", "workspace/inline.txt hello world", si, fs
        )
        assert result.startswith("[OK]"), f"got: {result}"
        assert (tmp_path / "workspace" / "inline.txt").read_text(encoding="utf-8") == "hello world"
    finally:
        sub.close()
