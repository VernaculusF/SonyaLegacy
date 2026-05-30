"""Skill executor — runs registered skills and returns results.

Skills are Python modules with a `run(context: dict) -> str` entry point.
Built-in skills live in `sonya.skills.builtins.*`. Runtime skills (added
by Sonya through `skills.register_runtime`) live in
`~/.sonya/runtime_skills/<skill_id>.py` and are imported via SourceFileLoader.

Resolution order for a skill_id:

1. ``Skill.module_path`` from the registry row (preferred — set on
   register / migrated by v22). May be a dotted python path
   ("sonya.skills.builtins.memory_search") or a filesystem path
   ("/home/sonya/.sonya/runtime_skills/foo.py").
2. Legacy ``_BUILTIN_SKILLS`` dict — kept so substrates that pre-date
   the v22 migration still work without a re-register call.

Executor enforces trust-level activation check before running.
"""

from __future__ import annotations

import importlib
import importlib.util
from pathlib import Path
from typing import Any

from sonya.skills.activation import activate_or_raise, SkillActivationDeniedError
from sonya.skills.registry import SkillRegistry, SkillNotFoundError
from sonya.skills.skill import Skill
from sonya.state.substrate import Substrate


# Legacy dotted-path mapping. Kept for substrates that haven't been
# migrated to v22 yet (where Skill.module_path may be empty).
_BUILTIN_SKILLS: dict[str, str] = {
    "skill-memory-search": "sonya.skills.builtins.memory_search",
    "skill-identity-check": "sonya.skills.builtins.identity_check",
    "skill-dialog-tone": "sonya.skills.builtins.dialog_tone",
}


def runtime_skills_dir() -> Path:
    """Where runtime-registered skills are stored on disk."""
    p = Path.home() / ".sonya" / "runtime_skills"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _import_module_from_spec(skill_id: str, module_path: str):
    """Import a skill module given a dotted path or filesystem path.

    Filesystem paths are loaded via ``importlib.util.spec_from_file_location``
    so runtime-installed skill files don't need to be on sys.path.
    """
    if module_path.endswith(".py") or "/" in module_path or "\\" in module_path:
        path = Path(module_path).expanduser()
        if not path.is_absolute():
            path = (runtime_skills_dir() / path).resolve()
        if not path.exists():
            raise ImportError(f"skill module file not found: {path}")
        spec = importlib.util.spec_from_file_location(
            f"sonya_runtime_skills.{skill_id.replace('-', '_')}", path
        )
        if spec is None or spec.loader is None:
            raise ImportError(f"cannot build spec for {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        return module
    return importlib.import_module(module_path)


class SkillExecutor:
    """Runs skills by skill_id. Checks trust, imports module, calls run()."""

    def __init__(self, registry: SkillRegistry, substrate: Substrate) -> None:
        self._registry = registry
        self._substrate = substrate

    def _resolve_module_path(self, skill: Skill) -> str | None:
        if skill.module_path:
            return skill.module_path
        return _BUILTIN_SKILLS.get(skill.skill_id)

    def execute(
        self,
        skill_id: str,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Run a skill by id. Returns observation string."""
        # Resolve skill
        try:
            skill = self._registry.get(skill_id)
        except SkillNotFoundError:
            return f"[ERROR] skill {skill_id!r} not found in registry"

        # Trust check
        try:
            activate_or_raise(skill)
        except SkillActivationDeniedError as exc:
            return f"[BLOCKED] {exc}"

        module_path = self._resolve_module_path(skill)
        if not module_path:
            available = ", ".join(_BUILTIN_SKILLS.keys()) or "(none)"
            return (
                f"[ERROR] skill {skill_id!r} has no module path. "
                f"Register via skills.register_runtime, or pick a legacy "
                f"builtin: {available}"
            )

        try:
            module = _import_module_from_spec(skill_id, module_path)
        except ImportError as exc:
            return f"[ERROR] cannot import skill module {module_path}: {exc}"
        except Exception as exc:  # syntax errors etc.
            return (
                f"[ERROR] skill module {module_path} failed to load: "
                f"{type(exc).__name__}: {exc}"
            )

        run_fn = getattr(module, "run", None)
        if run_fn is None:
            return f"[ERROR] skill module {module_path} has no run() function"

        # Build context
        ctx = dict(context or {})
        ctx.setdefault("substrate", self._substrate)
        ctx.setdefault("skill_id", skill_id)

        try:
            result = run_fn(ctx)
        except Exception as exc:
            return f"[ERROR] skill {skill_id} crashed: {type(exc).__name__}: {exc}"

        return str(result) if result is not None else "(skill returned nothing)"

    def list_available(self) -> str:
        """List every registered skill with status, trust and module path.

        v22+: enumerates from substrate (so runtime-registered skills show
        up). Legacy ``_BUILTIN_SKILLS`` ids that aren't in the registry
        are appended at the bottom as "NOT REGISTERED".
        """
        try:
            rows = self._registry.list_all()
        except Exception:
            rows = []

        seen: set[str] = set()
        lines: list[str] = ["Available skills:"]
        for skill in rows:
            seen.add(skill.skill_id)
            module_path = self._resolve_module_path(skill) or "(no module)"
            lines.append(
                f"  - {skill.skill_id}: {module_path} "
                f"[{skill.status} (trust={skill.trust_level.value})]"
            )

        for sid, mpath in _BUILTIN_SKILLS.items():
            if sid in seen:
                continue
            lines.append(
                f"  - {sid}: {mpath} "
                f"[NOT REGISTERED — call skills.register_builtins first]"
            )

        if len(lines) == 1:
            lines.append("  (registry empty — call skills.register_builtins)")

        return "\n".join(lines)


__all__ = ["SkillExecutor", "runtime_skills_dir"]
