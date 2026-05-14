from __future__ import annotations

import ast
from pathlib import Path

import pytest

_SONYA_ROOT = Path(__file__).resolve().parent.parent.parent / "src" / "sonya"


def _python_files(folder: Path) -> list[Path]:
    return [p for p in folder.rglob("*.py") if "__pycache__" not in p.parts]


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.append(node.module)
    return names


def test_state_does_not_import_runtime() -> None:
    state_dir = _SONYA_ROOT / "state"
    offenders: list[tuple[Path, str]] = []
    for file in _python_files(state_dir):
        for name in _imports(file):
            if name.startswith("sonya.runtime"):
                offenders.append((file, name))
    assert not offenders, f"state must not import runtime: {offenders}"


def test_runtime_uses_only_state_public_api() -> None:
    runtime_dir = _SONYA_ROOT / "runtime"
    offenders: list[tuple[Path, str]] = []
    for file in _python_files(runtime_dir):
        for name in _imports(file):
            # runtime can import sonya.state (public package) but not deeper modules.
            if name.startswith("sonya.state.") and name != "sonya.state":
                offenders.append((file, name))
    assert not offenders, (
        "runtime must use sonya.state public API only, not private modules: "
        f"{offenders}"
    )


def test_state_public_api_is_explicit() -> None:
    state_init = _SONYA_ROOT / "state" / "__init__.py"
    text = state_init.read_text(encoding="utf-8")
    assert "__all__" in text, "state/__init__.py must declare __all__"


def test_runtime_public_api_is_explicit() -> None:
    runtime_init = _SONYA_ROOT / "runtime" / "__init__.py"
    text = runtime_init.read_text(encoding="utf-8")
    assert "__all__" in text, "runtime/__init__.py must declare __all__"
