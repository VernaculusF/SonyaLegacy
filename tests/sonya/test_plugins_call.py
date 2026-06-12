"""plugins.call should parse JSON-shaped args automatically.

Live audit 31.05: Sonya wasted 10+ steps debugging the run(ctx) contract
because docs claimed `args` is dict but dispatcher passed raw string.
Now: dict/list literals → JSON parse; raw text → plain string; empty → {}.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from sonya.subject.agent_session import _h_plugins_call, _ToolContext
from sonya.tools import hot_loader


@pytest.fixture()
def plugins_dir(tmp_path: Path, monkeypatch):
    """Redirect plugins to a tmp dir so tests don't pollute repo."""
    monkeypatch.setattr(hot_loader, "_PLUGINS_DIR", tmp_path)
    monkeypatch.setattr(hot_loader, "_loaded_plugins", {})
    yield tmp_path


def _write_plugin(plugins_dir: Path, name: str, body: str) -> None:
    (plugins_dir / "__init__.py").write_text("", encoding="utf-8")
    (plugins_dir / f"{name}.py").write_text(body, encoding="utf-8")


def _ctx() -> _ToolContext:
    """Build a minimal _ToolContext — _h_plugins_call doesn't use any
    of the tool instances, only `arg`, so all fields can be None."""
    return _ToolContext(
        self_inspect=None,  # type: ignore[arg-type]
        filesystem=None,    # type: ignore[arg-type]
        selfmod=None,
        work=None,
        web=None,
        code=None,
        shell=None,
        memory=None,
        env=None,
        skills=None,
        outbound=None,
        outbound_sent=None,
    )


def test_plugin_receives_dict_when_args_are_json_object(plugins_dir: Path) -> None:
    _write_plugin(plugins_dir, "echo_dict", (
        "def run(args):\n"
        "    return {'received_type': type(args).__name__, 'value': args}\n"
    ))
    out = _h_plugins_call('echo_dict {"x": 1, "y": "two"}', _ctx())
    assert "'received_type': 'dict'" in out
    assert "'x': 1" in out
    assert "'y': 'two'" in out


def test_plugin_receives_list_when_args_are_json_array(plugins_dir: Path) -> None:
    _write_plugin(plugins_dir, "echo_list", (
        "def run(args):\n"
        "    return {'type': type(args).__name__, 'len': len(args)}\n"
    ))
    out = _h_plugins_call('echo_list [1,2,3,4]', _ctx())
    assert "'type': 'list'" in out
    assert "'len': 4" in out


def test_plugin_receives_string_for_plain_text(plugins_dir: Path) -> None:
    _write_plugin(plugins_dir, "echo_str", (
        "def run(args):\n"
        "    return {'type': type(args).__name__, 'value': args}\n"
    ))
    out = _h_plugins_call("echo_str hello world", _ctx())
    assert "'type': 'str'" in out
    assert "hello world" in out


def test_plugin_receives_empty_dict_when_no_args(plugins_dir: Path) -> None:
    _write_plugin(plugins_dir, "echo_empty", (
        "def run(args):\n"
        "    return {'type': type(args).__name__, 'value': args}\n"
    ))
    out = _h_plugins_call("echo_empty", _ctx())
    assert "'type': 'dict'" in out
    assert "{}" in out


def test_invalid_json_falls_back_to_raw_string(plugins_dir: Path) -> None:
    """{not json} → kept as raw string instead of crashing."""
    _write_plugin(plugins_dir, "echo_fallback", (
        "def run(args):\n"
        "    return type(args).__name__\n"
    ))
    out = _h_plugins_call('echo_fallback {not json}', _ctx())
    assert "str" in out


def test_plugin_crash_returns_error_string(plugins_dir: Path) -> None:
    _write_plugin(plugins_dir, "broken", (
        "def run(args):\n"
        "    raise RuntimeError('boom')\n"
    ))
    out = _h_plugins_call("broken", _ctx())
    assert "[ERROR]" in out
    assert "RuntimeError" in out
    assert "boom" in out


def test_missing_plugin_returns_error(plugins_dir: Path) -> None:
    out = _h_plugins_call("nonexistent_plugin", _ctx())
    assert "[ERROR]" in out


def test_plugin_without_run_returns_error(plugins_dir: Path) -> None:
    _write_plugin(plugins_dir, "no_run", "x = 1\n")
    out = _h_plugins_call("no_run", _ctx())
    assert "[ERROR]" in out
    assert "no run() function" in out
