"""Skills tool — agent-facing wrapper for skill execution.

Tools:
  skills.list — show registered + available skills
  skills.run <skill_id> [query or JSON context] — execute a skill
  skills.register_builtins — seed the 3 built-in skills into registry
  skills.register_runtime — register a NEW runtime skill from inline code

Block form for ``skills.register_runtime``:

    skill_id|name|purpose|trust_level
    <python source for the skill, must define run(ctx) -> str>

Example::

    skills.register_runtime
    skill-greet|Greet|Greeting helper|experimental
    def run(ctx):
        return "hi " + ctx.get("query", "")

The first line is metadata, everything after is module source. The source
is written to ``~/.sonya/runtime_skills/<skill_id>.py`` and a skills row is
created with ``module_path`` pointing at that file. The executor imports
via SourceFileLoader, so the new skill is callable immediately.

If the skill_id already exists with a different module_path, the row's
module_path is replaced (overwrite-in-place) so re-registering during
development just updates the code without requiring a new skill_id.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from sonya.skills.executor import SkillExecutor, runtime_skills_dir
from sonya.skills.registry import SkillRegistry, SkillAlreadyExistsError
from sonya.skills.skill import Skill
from sonya.skills.trust import TrustLevel
from sonya.state.substrate import Substrate


_TRUST_LOOKUP = {t.value: t for t in TrustLevel}
_VALID_SKILL_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{1,63}$")


class SkillsTool:
    """Agent-callable interface to skill system."""

    def __init__(self, substrate: Substrate) -> None:
        self._sub = substrate
        self._registry = SkillRegistry(substrate)
        self._executor = SkillExecutor(self._registry, substrate)

    def list_skills(self) -> str:
        return self._executor.list_available()

    def run(self, arg: str, *, extra_context: dict[str, Any] | None = None) -> str:
        """Run a skill. arg = '<skill_id>' or '<skill_id> <query>'."""
        parts = arg.strip().split(None, 1)
        if not parts:
            return "[ERROR] skills.run needs: <skill_id> [query]"
        skill_id = parts[0]
        query = parts[1] if len(parts) > 1 else ""

        ctx: dict[str, Any] = dict(extra_context or {})
        ctx["query"] = query
        ctx["user_input"] = query

        return self._executor.execute(skill_id, context=ctx)

    def register_builtins(self) -> str:
        """Seed the 3 built-in skills into the registry (idempotent)."""
        builtins = [
            Skill(
                skill_id="skill-memory-search",
                name="memory-search",
                purpose="Semantic recall: find relevant past events by meaning.",
                version="1.0.0",
                status="active",
                trust_level=TrustLevel.CORE_TRUSTED,
                activation_rules={"trigger": "query about past events"},
                allowed_tools=("memory.recall",),
                module_path="sonya.skills.builtins.memory_search",
            ),
            Skill(
                skill_id="skill-identity-check",
                name="identity-check",
                purpose="Self-verification: check identity record integrity.",
                version="1.0.0",
                status="active",
                trust_level=TrustLevel.CORE_TRUSTED,
                activation_rules={"trigger": "periodic / on drift signal"},
                allowed_tools=("self_inspect.identity",),
                module_path="sonya.skills.builtins.identity_check",
            ),
            Skill(
                skill_id="skill-dialog-tone",
                name="dialog-tone",
                purpose="Analyze Ivan's recent tone and suggest response register.",
                version="1.0.0",
                status="active",
                trust_level=TrustLevel.TRUSTED,
                activation_rules={"trigger": "before each TG reply"},
                allowed_tools=(),
                module_path="sonya.skills.builtins.dialog_tone",
            ),
        ]
        registered = []
        for skill in builtins:
            try:
                self._registry.register(skill)
                registered.append(skill.skill_id)
            except SkillAlreadyExistsError:
                # Backfill module_path on substrates that pre-date v22.
                try:
                    existing = self._registry.get(skill.skill_id)
                    if not existing.module_path and skill.module_path:
                        self._registry.update_module_path(
                            skill.skill_id, skill.module_path
                        )
                        registered.append(f"{skill.skill_id} (module_path backfilled)")
                    else:
                        registered.append(f"{skill.skill_id} (already exists)")
                except Exception:
                    registered.append(f"{skill.skill_id} (already exists)")
        return f"[OK] registered: {', '.join(registered)}"

    def register_runtime(self, arg: str) -> str:
        """Register a runtime skill from inline source code.

        See module docstring for the block form. Returns ``[OK]`` plus the
        path the source was written to, or ``[ERROR]`` with a reason.
        """
        text = (arg or "").lstrip("\n")
        if "\n" not in text:
            return (
                "[ERROR] skills.register_runtime needs: "
                "skill_id|name|purpose|trust_level\\n<python source>"
            )
        meta_line, source = text.split("\n", 1)
        parts = [p.strip() for p in meta_line.split("|")]
        if len(parts) < 3:
            return (
                "[ERROR] meta line needs at least: "
                "skill_id|name|purpose [|trust_level]"
            )
        skill_id = parts[0]
        if not _VALID_SKILL_ID.match(skill_id):
            return (
                "[ERROR] invalid skill_id (use lowercase letters, digits, "
                "'-' or '_', 2-64 chars)"
            )
        name = parts[1]
        purpose = parts[2]
        trust_raw = parts[3] if len(parts) > 3 and parts[3] else "experimental"
        trust = _TRUST_LOOKUP.get(trust_raw.lower())
        if trust is None:
            return (
                f"[ERROR] unknown trust_level {trust_raw!r}. "
                f"Valid: {', '.join(_TRUST_LOOKUP)}"
            )

        if not source.strip():
            return "[ERROR] empty skill source"
        if "def run(" not in source:
            return "[ERROR] skill source must define `def run(ctx):`"

        # Compile-check before writing — surfaces syntax errors immediately
        # instead of failing on first execute.
        try:
            compile(source, f"<runtime_skill:{skill_id}>", "exec")
        except SyntaxError as exc:
            return f"[ERROR] syntax: {exc}"

        target = runtime_skills_dir() / f"{skill_id}.py"
        try:
            target.write_text(source, encoding="utf-8")
        except OSError as exc:
            return f"[ERROR] could not write {target}: {exc}"

        skill = Skill(
            skill_id=skill_id,
            name=name,
            purpose=purpose,
            version="0.1.0",
            status="active",
            trust_level=trust,
            module_path=str(target),
        )
        try:
            self._registry.register(skill)
            note = "registered"
        except SkillAlreadyExistsError:
            self._registry.update_module_path(skill_id, str(target))
            note = "module_path updated (overwrite)"

        return f"[OK] {skill_id}: {note} → {target}"


__all__ = ["SkillsTool"]
