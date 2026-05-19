"""Tests for Этап E — web/code/shell tools."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from sonya.harness.approval import ApprovalManager, ApprovalStatus
from sonya.state import Substrate
from sonya.state.continuity_stream import ContinuityStream
from sonya.tools.code_tool import CodeTool
from sonya.tools.shell_tool import ShellTool


# ---------- code.exec ----------

def test_code_exec_simple_print() -> None:
    tool = CodeTool(timeout_seconds=10)
    out = tool.exec_python("print('hello world')")
    assert "[exit 0]" in out
    assert "hello world" in out


def test_code_exec_captures_stderr() -> None:
    tool = CodeTool(timeout_seconds=10)
    out = tool.exec_python("import sys; sys.stderr.write('oops\\n'); sys.exit(2)")
    assert "[exit 2]" in out
    assert "oops" in out


def test_code_exec_timeout() -> None:
    tool = CodeTool(timeout_seconds=1)
    out = tool.exec_python("import time; time.sleep(5)")
    assert "[TIMEOUT]" in out


def test_code_exec_empty_arg_rejected() -> None:
    tool = CodeTool()
    out = tool.exec_python("   ")
    assert "[ERROR]" in out


def test_code_exec_isolated_cwd() -> None:
    """Each call should run in a fresh tempdir; later calls don't see earlier files."""
    tool = CodeTool(timeout_seconds=10)
    a = tool.exec_python("open('marker', 'w').write('x'); print('wrote')")
    assert "wrote" in a
    b = tool.exec_python("import os; print('exists' if os.path.exists('marker') else 'gone')")
    assert "gone" in b


# ---------- shell.run / pip.install (gated) ----------

@pytest.fixture()
def shell(tmp_path: Path):
    sub = Substrate.open(tmp_path / "s.db")
    yield ShellTool(
        sub,
        principal_id="ivan",
        stream=ContinuityStream(sub),
        timeout_seconds=10,
    ), sub
    sub.close()


def test_shell_run_first_call_creates_pending(shell) -> None:
    tool, sub = shell
    out = tool.run_shell("echo hi")
    assert "[PENDING_APPROVAL:" in out
    pending = ApprovalManager(sub).list_pending()
    assert len(pending) == 1
    assert pending[0].action.startswith("shell.run:")
    assert pending[0].scope == "echo hi"


def test_shell_run_second_call_same_command_does_not_duplicate(shell) -> None:
    tool, sub = shell
    tool.run_shell("echo hi")
    tool.run_shell("echo hi")
    pending = ApprovalManager(sub).list_pending()
    assert len(pending) == 1


def test_shell_run_after_approval_executes(shell) -> None:
    tool, sub = shell
    out1 = tool.run_shell("echo sonya-was-here")
    req_id = out1.split("[PENDING_APPROVAL:")[1].split("]")[0].strip()

    ApprovalManager(sub).approve(req_id, by_principal_id="ivan")

    out2 = tool.run_shell("echo sonya-was-here")
    # On Windows the test may run under cmd shim; we use /bin/sh which won't exist
    # there. Skip the assertion if the spawn failed.
    if sys.platform.startswith("win"):
        assert "[OK approved=" in out2 or "[SPAWN FAIL]" in out2
    else:
        assert "[OK approved=" in out2
        assert "exit: 0" in out2
        assert "sonya-was-here" in out2


def test_shell_run_denied(shell) -> None:
    tool, sub = shell
    out1 = tool.run_shell("rm -rf /")
    req_id = out1.split("[PENDING_APPROVAL:")[1].split("]")[0].strip()
    ApprovalManager(sub).deny(req_id, by_principal_id="ivan")
    out2 = tool.run_shell("rm -rf /")
    assert "[DENIED]" in out2


def test_pip_install_pending(shell) -> None:
    tool, sub = shell
    out = tool.install_pip("requests==2.31.0")
    assert "[PENDING_APPROVAL:" in out
    pending = ApprovalManager(sub).list_pending()
    assert len(pending) == 1
    assert pending[0].action.startswith("pip.install:")


def test_pip_install_rejects_injection(shell) -> None:
    tool, _ = shell
    out = tool.install_pip("foo; rm -rf /")
    assert "[ERROR]" in out
    assert "invalid characters" in out


def test_shell_run_empty_command_rejected(shell) -> None:
    tool, _ = shell
    out = tool.run_shell("   ")
    assert "[ERROR]" in out


def test_two_different_commands_separate_approvals(shell) -> None:
    tool, sub = shell
    tool.run_shell("ls /")
    tool.run_shell("ls /tmp")
    pending = ApprovalManager(sub).list_pending()
    assert len(pending) == 2


# ---------- web (offline mocked) ----------

def test_web_search_uses_ddg_html() -> None:
    from sonya.tools.web_tool import WebTool

    sample_html = (
        '<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com">Example</a>'
        '<a class="result__snippet">An example snippet</a>'
    )

    class _Resp:
        status = 200

        async def read(self):
            return sample_html.encode("utf-8")

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    class _Sess:
        def get(self, url):
            return _Resp()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    with patch("aiohttp.ClientSession", return_value=_Sess()):
        out = WebTool().search("example query")
    assert "Example" in out
    assert "https://example.com" in out
    assert "An example snippet" in out


def test_web_fetch_rejects_non_http() -> None:
    from sonya.tools.web_tool import WebTool

    out = WebTool().fetch("file:///etc/passwd")
    assert "[ERROR]" in out
    assert "http(s)" in out


def test_web_search_empty_query() -> None:
    from sonya.tools.web_tool import WebTool

    out = WebTool().search("")
    assert "[ERROR]" in out



# ====================================================================
# Async-context regression: tool dispatcher sits inside a running event
# loop, so WebTool.search/fetch must NOT spawn 'coroutine never awaited'
# warnings or fail with RuntimeError when called from async code.
# ====================================================================


async def test_web_search_runs_inside_event_loop_without_warnings():
    """Calling WebTool.search from inside a running event loop must succeed
    and not emit 'coroutine was never awaited' warnings."""
    import warnings
    from unittest.mock import patch
    from sonya.tools.web_tool import WebTool

    sample_html = (
        '<a class="result__a" href="https://example.com">Title</a>'
        '<a class="result__snippet">Snippet</a>'
    )

    class _Resp:
        status = 200
        async def read(self):
            return sample_html.encode("utf-8")
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return None

    class _Sess:
        def __init__(self, *a, **kw): pass
        def get(self, url): return _Resp()
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return None

    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        with patch("aiohttp.ClientSession", return_value=_Sess()):
            out = WebTool().search("test query")
    assert "Title" in out
    assert "https://example.com" in out
