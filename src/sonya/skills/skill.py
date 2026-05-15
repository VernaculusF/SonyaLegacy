from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sonya.skills.trust import TrustLevel


@dataclass(frozen=True, slots=True)
class Skill:
    """Skill artifact with all 14 fields from SKILL_SYSTEM_PLAN §4.

    A skill is a managed unit of behavior with identity, version,
    trust level, activation rules, and lifecycle.
    """

    skill_id: str
    name: str
    purpose: str
    version: str = "0.1.0"
    status: str = "active"  # active, deprecated, archived
    trust_level: TrustLevel = TrustLevel.EXPERIMENTAL
    activation_rules: dict[str, Any] = field(default_factory=dict)
    dependencies: tuple[str, ...] = field(default_factory=tuple)
    allowed_tools: tuple[str, ...] = field(default_factory=tuple)
    forbidden_zones: tuple[str, ...] = field(default_factory=tuple)
    tests: tuple[str, ...] = field(default_factory=tuple)
    metrics: dict[str, Any] = field(default_factory=dict)
    trace_tags: tuple[str, ...] = field(default_factory=tuple)
    history: tuple[str, ...] = field(default_factory=tuple)
