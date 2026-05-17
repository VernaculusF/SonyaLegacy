"""Tests for module_loader — sandbox testing + path-to-dotted conversion."""
from __future__ import annotations

import sys

from sonya.tools.module_loader import (
    discover_subclasses,
    path_to_dotted,
    sandbox_test,
)


def test_path_to_dotted_basic() -> None:
    assert path_to_dotted("src/sonya/channels/discord.py") == "sonya.channels.discord"
    assert path_to_dotted("src/sonya/main.py") == "sonya.main"
    assert path_to_dotted("src/sonya/channels/__init__.py") == "sonya.channels"


def test_path_to_dotted_strips_src() -> None:
    assert path_to_dotted("src/sonya/tools/foo.py") == "sonya.tools.foo"


def test_sandbox_test_passes_clean_code() -> None:
    result = sandbox_test("anything.py", "X = 1\ndef f():\n    return X + 1\n")
    assert result["ok"] is True
    assert "X" in result["exports"] or "f" in result["exports"]
    assert result["error"] == ""


def test_sandbox_test_catches_syntax_error() -> None:
    result = sandbox_test("anything.py", "def broken( :\n    pass\n")
    assert result["ok"] is False
    assert "SyntaxError" in result["error"]


def test_sandbox_test_catches_import_error() -> None:
    result = sandbox_test("anything.py", "import nonexistent_module_xyz123\n")
    assert result["ok"] is False
    assert "ModuleNotFoundError" in result["error"] or "ImportError" in result["error"]


def test_sandbox_test_catches_top_level_exception() -> None:
    result = sandbox_test("anything.py", "raise ValueError('top-level boom')\n")
    assert result["ok"] is False
    assert "ValueError" in result["error"]


def test_sandbox_test_does_not_pollute_sys_modules() -> None:
    pre_modules = set(sys.modules.keys())
    sandbox_test("anything.py", "X = 42\n")
    post_modules = set(sys.modules.keys())
    # Sandbox name was unique; should not leak
    sandbox_only = post_modules - pre_modules
    sandbox_only.discard("__pycache__")  # may be touched
    # Any leftover sandbox module is a leak
    leaks = [m for m in sandbox_only if m.startswith("_sonya_sandbox_")]
    assert leaks == []


def test_discover_subclasses_finds_protocol_implementations() -> None:
    """discover_subclasses should find classes that satisfy a Protocol."""
    from typing import Protocol, runtime_checkable

    @runtime_checkable
    class Greeter(Protocol):
        def greet(self) -> str: ...

    class HelloImpl:
        name = "hello"
        def greet(self) -> str:
            return "hello"

    class NotAGreeter:
        def something_else(self) -> str:
            return "x"

    # Create a fake module-like object
    import types
    mod = types.ModuleType("fake")
    mod.HelloImpl = HelloImpl
    mod.NotAGreeter = NotAGreeter

    subclasses = discover_subclasses(mod, Greeter)
    assert HelloImpl in subclasses
    assert NotAGreeter not in subclasses
