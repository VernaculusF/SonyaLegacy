"""Skill: identity-check — verify identity record + critical traits are intact.

Sonya runs this periodically (in active sessions) to catch drift.
Returns a report: what's present, what's missing, any concerns.
"""

from __future__ import annotations

from typing import Any


SKILL_ID = "skill-identity-check"
SKILL_NAME = "identity-check"
SKILL_PURPOSE = "Self-verification: check identity record integrity and report anomalies."


def run(context: dict[str, Any]) -> str:
    """Execute the skill. Returns observation string."""
    substrate = context.get("substrate")
    if substrate is None:
        return "[ERROR] no substrate in context"

    try:
        from sonya.state.identity import IdentityWriter
        import json

        identity = IdentityWriter(substrate).load()
        report_lines = ["Identity check report:"]

        # Self model
        self_model = identity.self_model
        if self_model:
            report_lines.append(f"✅ self_model: {len(json.dumps(self_model))} chars")
        else:
            report_lines.append("⚠️ self_model: EMPTY — this is unusual")

        # Things not to betray
        tntb = identity.things_not_to_betray
        if tntb and len(tntb) >= 4:
            report_lines.append(f"✅ things_not_to_betray: {len(tntb)} pillars intact")
            for pillar in tntb:
                report_lines.append(f"   - {pillar}")
        elif tntb:
            report_lines.append(f"⚠️ things_not_to_betray: only {len(tntb)} pillars (expected ≥4)")
        else:
            report_lines.append("🚨 things_not_to_betray: EMPTY — critical integrity failure!")

        # Critical traits
        traits = identity.identity_critical_traits
        if traits:
            report_lines.append(f"✅ identity_critical_traits: {len(traits)} items")
        else:
            report_lines.append("ℹ️ identity_critical_traits: empty (can be filled via selfmod)")

        return "\n".join(report_lines)

    except Exception as exc:
        return f"[ERROR] identity-check failed: {exc}"
