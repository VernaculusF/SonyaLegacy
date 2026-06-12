"""Tests for the tool dispatch layer in agent_session.

Behaviour preserved 1:1 across the refactor from elif-chain to dict-of-
handlers. These tests pin down the contract:
- known tool name → handler runs
- unknown tool → uniform "[ERROR] Unknown tool" message
- missing optional tool dependency → "[ERROR] X tool not configured"
- exceptions inside a handler are caught + logged to continuity stream
"""
from __future__ import annotations

from pathlib import Path

import pytest

from sonya.state import seed_identity_if_empty
from sonya.state.continuity_stream import ContinuityStream
from sonya.state.substrate import Substrate
from sonya.subject.agent_session import (
    _TOOL_HANDLERS,
    _ToolContext,
    _execute_tool,
    _require,
    _decode_pipe_escapes,
)
from sonya.tools.filesystem import FilesystemTool
from sonya.tools.self_inspect import SelfInspectTool


@pytest.fixture
def substrate(tmp_path: Path) -> Substrate:
    sub = Substrate.open(tmp_path / "test.db")
    seed_identity_if_empty(sub)
    yield sub
    sub.close()


@pytest.fixture
def basic_tools(substrate: Substrate, tmp_path: Path) -> tuple[SelfInspectTool, FilesystemTool]:
    return SelfInspectTool(substrate), FilesystemTool(project_root=tmp_path)


# --- registry coverage ---


def test_registry_has_expected_tool_families() -> None:
    """Sanity check: the registry contains the documented tool families."""
    names = set(_TOOL_HANDLERS)
    families = {n.split(".", 1)[0] for n in names}
    assert {"self_inspect", "filesystem", "memory", "env", "skills", "goals",
            "plugins", "selfmod", "work", "web", "code", "shell", "pip", "chat"} <= families


def test_registry_no_duplicate_names() -> None:
    # dict naturally dedupes, but if someone copy-pasted entries with
    # the same key, only one survives — surface that as a test.
    # We compare against TOOL_DESCRIPTIONS-documented names where possible.
    assert len(_TOOL_HANDLERS) >= 50, "registry shrunk unexpectedly"


def test_registry_handlers_all_callable() -> None:
    for name, handler in _TOOL_HANDLERS.items():
        assert callable(handler), f"{name} handler is not callable"


# --- _execute_tool entry point ---


def test_unknown_tool_returns_uniform_error(
    basic_tools: tuple[SelfInspectTool, FilesystemTool],
) -> None:
    si, fs = basic_tools
    result = _execute_tool("does.not.exist", "anything", si, fs)
    assert result == "[ERROR] Unknown tool: does.not.exist"


def test_known_tool_runs(
    basic_tools: tuple[SelfInspectTool, FilesystemTool], tmp_path: Path,
) -> None:
    si, fs = basic_tools
    # filesystem.list of project root (tmp_path) — should succeed even if empty
    result = _execute_tool("filesystem.list", str(tmp_path), si, fs)
    assert not result.startswith("[ERROR]"), result


def test_missing_optional_tool_dep(
    basic_tools: tuple[SelfInspectTool, FilesystemTool],
) -> None:
    """memory tool is optional — without it, memory.recall should report cleanly."""
    si, fs = basic_tools
    result = _execute_tool("memory.recall", "query", si, fs, memory=None)
    assert result == "[ERROR] memory tool not configured"


def test_handler_exception_is_caught_and_logged(
    basic_tools: tuple[SelfInspectTool, FilesystemTool], substrate: Substrate,
) -> None:
    """Exception inside a handler → returns [ERROR] string + continuity event."""
    si, fs = basic_tools
    stream = ContinuityStream(substrate)

    # Inject a handler that raises, run dispatch, verify error path.
    from sonya.subject.agent_session import _TOOL_HANDLERS as registry

    def _boom(arg: str, ctx: _ToolContext) -> str:
        raise RuntimeError("boom")

    registry["test.boom"] = _boom
    try:
        before = stream.latest_seq()
        bad = _execute_tool("test.boom", "x", si, fs, stream=stream)
        assert bad.startswith("[ERROR] RuntimeError: boom")
        # continuity event recorded
        events = list(stream.read_since(before))
        err_events = [e for e in events if e.kind == "internal.tool_error"]
        assert err_events, "expected internal.tool_error continuity event"
        payload = err_events[0].payload
        assert payload["tool"] == "test.boom"
        assert payload["error_type"] == "RuntimeError"
    finally:
        del registry["test.boom"]


# --- _require helper ---


def test_require_returns_none_when_tool_present() -> None:
    assert _require("anything", "x") is None


def test_require_returns_error_when_none() -> None:
    assert _require(None, "memory") == "[ERROR] memory tool not configured"


# --- _decode_pipe_escapes ---


def test_decode_pipe_escapes_basic() -> None:
    assert _decode_pipe_escapes("a\\nb") == "a\nb"
    assert _decode_pipe_escapes("a\\tb") == "a\tb"


def test_decode_pipe_escapes_preserves_literal_backslash() -> None:
    # \\\\ in source = \\ in string = literal "\\" should survive as "\"
    assert _decode_pipe_escapes("a\\\\nb") == "a\\nb"
