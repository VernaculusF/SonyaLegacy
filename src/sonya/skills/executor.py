"""Skill executor — runs registered skills and returns results.

Skills are Python modules with a `run(context: dict) -> str` entry point.
Built-in skills live in `sonya.skills.builtins.*`. User-created skills
can also be registered if they follow the same contract.

Executor enforces trust-level activation check before running.
"""

from __future__ import annotations

import importlib
from typing import Any

from sonya.skills.activation import activate_or_raise, SkillActivationDeniedError
from sonya.skills.registry import SkillRegistry, SkillNotFoundError
from sonya.skills.skill import Skill
from sonya.state.substrate import Substrate


# Mapping from skill_id to module dotted path.
# Built-in skills are auto-discovered; user skills would be added here too.
_BUILTIN_SKILLS: dict[str, str] = {
    "skill-memory-search": "sonya.skills.builtins.memory_search",
    "skill-identity-check": "sonya.skills.builtins.identity_check",
    "skill-dialog-tone": "sonya.skills.builtins.dialog_tone",
}


class SkillExecutor:
    """Runs skills by skill_id. Checks trust, imports module, calls run()."""

    def __init__(self, registry: SkillRegistry, substrate: Substrate) -> None:
        self._registry = registry
        self._substrate = substrate

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

        # Find module
        module_path = _BUILTIN_SKILLS.get(skill_id)
        if module_path is None:
            return (
                f"[ERROR] skill {skill_id!r} has no registered module. "
                f"Only built-in skills are executable right now: "
                f"{', '.join(_BUILTIN_SKILLS.keys())}"
            )

        # Import + run
        try:
            module = importlib.import_module(module_path)
        except ImportError as exc:
            return f"[ERROR] cannot import skill module {module_path}: {exc}"

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
        """List all executable skills."""
        lines = ["Available skills:"]
        for sid, mod in _BUILTIN_SKILLS.items():
            try:
                skill = self._registry.get(sid)
                status = f"{skill.status} (trust={skill.trust_level.value})"
            except SkillNotFoundError:
                status = "NOT REGISTERED — call skills.register first"
            lines.append(f"  - {sid}: {mod} [{status}]")
        return "\n".join(lines)


__all__ = ["SkillExecutor"]
