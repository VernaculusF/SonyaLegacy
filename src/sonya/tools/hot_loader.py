"""Hot-load tool modules without process restart.

Sonya can write a new tool file to src/sonya/tools/plugins/,
then call hot_loader.load_plugin("module_name") to make it available
in the current process. No restart needed.

This is the self-improvement mechanism: she writes code → it becomes available.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path
from typing import Any


_PLUGINS_DIR = Path(__file__).parent / "plugins"
_loaded_plugins: dict[str, Any] = {}


def ensure_plugins_dir() -> Path:
    """Create plugins directory if it doesn't exist."""
    _PLUGINS_DIR.mkdir(parents=True, exist_ok=True)
    init_file = _PLUGINS_DIR / "__init__.py"
    if not init_file.exists():
        init_file.write_text("", encoding="utf-8")
    return _PLUGINS_DIR


def load_plugin(module_name: str) -> Any:
    """Load or reload a plugin module from tools/plugins/.

    Returns the module object. Raises ImportError if not found.
    """
    ensure_plugins_dir()
    module_path = _PLUGINS_DIR / f"{module_name}.py"
    if not module_path.exists():
        raise ImportError(f"Plugin not found: {module_path}")

    full_name = f"sonya.tools.plugins.{module_name}"

    if full_name in sys.modules:
        # Reload existing
        module = importlib.reload(sys.modules[full_name])
    else:
        # Load new
        spec = importlib.util.spec_from_file_location(full_name, module_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load spec for {module_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[full_name] = module
        spec.loader.exec_module(module)

    _loaded_plugins[module_name] = module
    return module


def list_plugins() -> list[str]:
    """List available plugin module names."""
    ensure_plugins_dir()
    return [p.stem for p in _PLUGINS_DIR.glob("*.py") if p.stem != "__init__"]


def get_plugin(module_name: str) -> Any | None:
    """Get an already-loaded plugin."""
    return _loaded_plugins.get(module_name)
