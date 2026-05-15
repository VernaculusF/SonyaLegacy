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


def test_state_does_not_import_brain_layers() -> None:
    """state is the lowest layer; providers and harness sit above it."""
    state_dir = _SONYA_ROOT / "state"
    offenders: list[tuple[Path, str]] = []
    for file in _python_files(state_dir):
        for name in _imports(file):
            if name.startswith("sonya.providers") or name.startswith("sonya.harness"):
                offenders.append((file, name))
    assert not offenders, (
        f"state must not import providers/harness (state is the lowest layer): "
        f"{offenders}"
    )


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


def test_runtime_does_not_import_brain_layers() -> None:
    """runtime is shell; providers and harness are brain. Only main.py glues them."""
    runtime_dir = _SONYA_ROOT / "runtime"
    offenders: list[tuple[Path, str]] = []
    for file in _python_files(runtime_dir):
        for name in _imports(file):
            if name.startswith("sonya.providers") or name.startswith("sonya.harness"):
                offenders.append((file, name))
    assert not offenders, (
        "runtime is shell-side: providers/harness import is forbidden, "
        f"only main.py composes them: {offenders}"
    )


def test_providers_does_not_import_runtime_or_harness() -> None:
    """providers is brain substrate; it may import state but not shell or harness."""
    providers_dir = _SONYA_ROOT / "providers"
    offenders: list[tuple[Path, str]] = []
    for file in _python_files(providers_dir):
        for name in _imports(file):
            if name.startswith("sonya.runtime") or name.startswith("sonya.harness"):
                offenders.append((file, name))
    assert not offenders, (
        f"providers must not import runtime or harness: {offenders}"
    )


def test_harness_does_not_import_runtime_or_providers() -> None:
    """harness sits over state/principals; bridge to providers happens above it."""
    harness_dir = _SONYA_ROOT / "harness"
    offenders: list[tuple[Path, str]] = []
    for file in _python_files(harness_dir):
        for name in _imports(file):
            if name.startswith("sonya.runtime") or name.startswith("sonya.providers"):
                offenders.append((file, name))
    assert not offenders, (
        f"harness must not import runtime or providers: {offenders}"
    )


def test_state_public_api_is_explicit() -> None:
    state_init = _SONYA_ROOT / "state" / "__init__.py"
    text = state_init.read_text(encoding="utf-8")
    assert "__all__" in text, "state/__init__.py must declare __all__"


def test_runtime_public_api_is_explicit() -> None:
    runtime_init = _SONYA_ROOT / "runtime" / "__init__.py"
    text = runtime_init.read_text(encoding="utf-8")
    assert "__all__" in text, "runtime/__init__.py must declare __all__"


def test_providers_public_api_is_explicit() -> None:
    providers_init = _SONYA_ROOT / "providers" / "__init__.py"
    text = providers_init.read_text(encoding="utf-8")
    assert "__all__" in text, "providers/__init__.py must declare __all__"


def test_harness_public_api_is_explicit() -> None:
    harness_init = _SONYA_ROOT / "harness" / "__init__.py"
    text = harness_init.read_text(encoding="utf-8")
    assert "__all__" in text, "harness/__init__.py must declare __all__"
