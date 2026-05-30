from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sonya.skills.skill import Skill
from sonya.skills.trust import TrustLevel
from sonya.state.substrate import Substrate


class SkillNotFoundError(KeyError):
    pass


class SkillAlreadyExistsError(RuntimeError):
    pass


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class SkillRegistry:
    """Persistent skill registry backed by substrate.

    See: SKILL_SYSTEM_PLAN §5.
    """

    def __init__(self, substrate: Substrate) -> None:
        self._sub = substrate

    def register(self, skill: Skill) -> Skill:
        existing = self._get_row(skill.skill_id)
        if existing is not None:
            raise SkillAlreadyExistsError(skill.skill_id)
        now = _utc_now_iso()
        self._sub.connection.execute(
            "INSERT INTO skills"
            "(skill_id, name, purpose, version, status, trust_level, "
            "activation_rules_json, dependencies_json, allowed_tools_json, "
            "forbidden_zones_json, tests_json, metrics_json, trace_tags_json, "
            "history_json, module_path, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                skill.skill_id,
                skill.name,
                skill.purpose,
                skill.version,
                skill.status,
                skill.trust_level.value,
                json.dumps(skill.activation_rules, ensure_ascii=False),
                json.dumps(list(skill.dependencies), ensure_ascii=False),
                json.dumps(list(skill.allowed_tools), ensure_ascii=False),
                json.dumps(list(skill.forbidden_zones), ensure_ascii=False),
                json.dumps(list(skill.tests), ensure_ascii=False),
                json.dumps(skill.metrics, ensure_ascii=False),
                json.dumps(list(skill.trace_tags), ensure_ascii=False),
                json.dumps(list(skill.history), ensure_ascii=False),
                skill.module_path or "",
                now,
            ),
        )
        self._sub.connection.commit()
        return skill

    def get(self, skill_id: str) -> Skill:
        row = self._get_row(skill_id)
        if row is None:
            raise SkillNotFoundError(skill_id)
        return _row_to_skill(row)

    def list_active(self) -> list[Skill]:
        cursor = self._sub.connection.execute(
            "SELECT skill_id, name, purpose, version, status, trust_level, "
            "activation_rules_json, dependencies_json, allowed_tools_json, "
            "forbidden_zones_json, tests_json, metrics_json, trace_tags_json, "
            "history_json, module_path FROM skills WHERE status = 'active' ORDER BY name"
        )
        return [_row_to_skill(row) for row in cursor.fetchall()]

    def list_all(self) -> list[Skill]:
        """Return every skill row regardless of status."""
        cursor = self._sub.connection.execute(
            "SELECT skill_id, name, purpose, version, status, trust_level, "
            "activation_rules_json, dependencies_json, allowed_tools_json, "
            "forbidden_zones_json, tests_json, metrics_json, trace_tags_json, "
            "history_json, module_path FROM skills ORDER BY name"
        )
        return [_row_to_skill(row) for row in cursor.fetchall()]

    def update_status(self, skill_id: str, status: str) -> Skill:
        self._sub.connection.execute(
            "UPDATE skills SET status = ? WHERE skill_id = ?",
            (status, skill_id),
        )
        self._sub.connection.commit()
        return self.get(skill_id)

    def update_module_path(self, skill_id: str, module_path: str) -> Skill:
        """Update an existing skill row's module_path.

        Useful when an Ivan-edit / selfmod relocates a skill module without
        re-creating its registry record.
        """
        self._sub.connection.execute(
            "UPDATE skills SET module_path = ? WHERE skill_id = ?",
            (module_path, skill_id),
        )
        self._sub.connection.commit()
        return self.get(skill_id)

    def _get_row(self, skill_id: str):
        return self._sub.connection.execute(
            "SELECT skill_id, name, purpose, version, status, trust_level, "
            "activation_rules_json, dependencies_json, allowed_tools_json, "
            "forbidden_zones_json, tests_json, metrics_json, trace_tags_json, "
            "history_json, module_path FROM skills WHERE skill_id = ?",
            (skill_id,),
        ).fetchone()


def _row_to_skill(row) -> Skill:
    return Skill(
        skill_id=row[0],
        name=row[1],
        purpose=row[2],
        version=row[3],
        status=row[4],
        trust_level=TrustLevel(row[5]),
        activation_rules=json.loads(row[6] or "{}"),
        dependencies=tuple(json.loads(row[7] or "[]")),
        allowed_tools=tuple(json.loads(row[8] or "[]")),
        forbidden_zones=tuple(json.loads(row[9] or "[]")),
        tests=tuple(json.loads(row[10] or "[]")),
        metrics=json.loads(row[11] or "{}"),
        trace_tags=tuple(json.loads(row[12] or "[]")),
        history=tuple(json.loads(row[13] or "[]")),
        module_path=(row[14] if len(row) > 14 and row[14] is not None else ""),
    )
