"""Skills tool — agent-facing wrapper for skill execution.

Tools:
  skills.list — show registered + available skills
  skills.run <skill_id> [query or JSON context] — execute a skill
  skills.register_builtins — seed the 3 built-in skills into registry
"""

from __future__ import annotations

import json
from typing import Any

from sonya.skills.executor import SkillExecutor
from sonya.skills.registry import SkillRegistry, SkillAlreadyExistsError
from sonya.skills.skill import Skill
from sonya.skills.trust import TrustLevel
from sonya.state.substrate import Substrate


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
            ),
        ]
        registered = []
        for skill in builtins:
            try:
                self._registry.register(skill)
                registered.append(skill.skill_id)
            except SkillAlreadyExistsError:
                registered.append(f"{skill.skill_id} (already exists)")
        return f"[OK] registered: {', '.join(registered)}"


__all__ = ["SkillsTool"]
