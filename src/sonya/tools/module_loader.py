"""Hot-reload arbitrary modules under src/sonya/, with sandbox test.

Sonya uses this to load/reload modules she just applied via selfmod.apply
without a process restart. Plus a sandbox test path that imports the
module in isolation and runs basic smoke checks (no name collisions
with the live process).

Limitations:
- Reloading a module doesn't update existing instances (e.g. already-running
  TelegramChannel). For channel additions, use ChannelRegistry hot-add.
- Reload doesn't propagate to modules that imported `from foo import Bar` —
  they keep the old reference. Caller is responsible for re-instantiating.
- Top-level constants in __init__.py won't refresh unless that module is reloaded too.
"""

from __future__ import annotations

import importlib
import importlib.util
import sys
import traceback
from pathlib import Path
from typing import Any


def reload_module(dotted_name: str) -> Any:
    """Import or reload a module by its dotted Python name.

    dotted_name examples: 'sonya.channels.discord', 'sonya.tools.web_search'.
    Returns the module object. Raises ImportError on failure.
    """
    if dotted_name in sys.modules:
        return importlib.reload(sys.modules[dotted_name])
    return importlib.import_module(dotted_name)


def path_to_dotted(rel_path: str) -> str:
    """Convert 'src/sonya/channels/discord.py' to 'sonya.channels.discord'."""
    p = Path(rel_path).as_posix().lstrip("/")
    if p.startswith("src/"):
        p = p[4:]
    if p.endswith("/__init__.py"):
        p = p[: -len("/__init__.py")]
    elif p.endswith(".py"):
        p = p[:-3]
    return p.replace("/", ".")


def sandbox_test(rel_path: str, content: str) -> dict[str, Any]:
    """Try to import-test the proposed content in an isolated namespace.

    Writes content to a temp .py file, imports it under a unique sandbox name,
    runs smoke checks: imports succeed, no top-level exceptions.

    Returns dict with keys: ok (bool), error (str), traceback (str), exports (list).
    Does NOT modify sys.modules of the real module.
    """
    import tempfile
    import os

    tmp_dir = tempfile.mkdtemp(prefix="sonya_sandbox_")
    tmp_file = Path(tmp_dir) / "_sandbox_module.py"
    tmp_file.write_text(content, encoding="utf-8")

    sandbox_name = f"_sonya_sandbox_{os.path.basename(tmp_dir)}"

    try:
        spec = importlib.util.spec_from_file_location(sandbox_name, tmp_file)
        if spec is None or spec.loader is None:
            return {
                "ok": False,
                "error": "could not build import spec",
                "traceback": "",
                "exports": [],
            }

        # Inject project root onto sys.path so `from sonya...` imports work
        project_root = str(Path(__file__).resolve().parent.parent.parent.parent / "src")
        path_added = False
        if project_root not in sys.path:
            sys.path.insert(0, project_root)
            path_added = True

        try:
            module = importlib.util.module_from_spec(spec)
            sys.modules[sandbox_name] = module
            spec.loader.exec_module(module)
            exports = [n for n in dir(module) if not n.startswith("_")]
            return {
                "ok": True,
                "error": "",
                "traceback": "",
                "exports": exports,
            }
        except Exception as err:
            return {
                "ok": False,
                "error": f"{type(err).__name__}: {err}",
                "traceback": traceback.format_exc(),
                "exports": [],
            }
        finally:
            sys.modules.pop(sandbox_name, None)
            if path_added:
                try:
                    sys.path.remove(project_root)
                except ValueError:
                    pass
    finally:
        try:
            tmp_file.unlink()
            Path(tmp_dir).rmdir()
        except Exception:
            pass


def discover_subclasses(module: Any, base_class: type) -> list[type]:
    """Find subclasses of `base_class` defined in `module`.

    Used by ChannelRegistry to auto-discover Channel implementations
    in newly-loaded channel modules.
    """
    result: list[type] = []
    for name in dir(module):
        if name.startswith("_"):
            continue
        obj = getattr(module, name)
        if isinstance(obj, type) and obj is not base_class:
            try:
                if issubclass(obj, base_class):
                    result.append(obj)
            except TypeError:
                pass
            # Protocol case: check by attribute presence
            try:
                if hasattr(base_class, "_is_protocol"):
                    # If it's a Protocol, check duck typing on methods
                    if all(hasattr(obj, attr) for attr in dir(base_class) if not attr.startswith("_")):
                        if obj not in result:
                            result.append(obj)
            except Exception:
                pass
    return result
