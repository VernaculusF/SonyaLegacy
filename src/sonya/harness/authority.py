from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from sonya.state import Principal, Substrate


class AuthorityDecision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    REQUIRE_APPROVAL = "require_approval"


@dataclass(frozen=True, slots=True)
class AuthorityRule:
    """One row in `harness_policy_rules`. Higher priority wins."""

    rule_id: int
    principal_id: str
    scope: str
    decision: AuthorityDecision
    priority: int = 0
    created_at: str = ""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AuthorityPolicy:
    """Persistent authority policy backed by substrate harness_policy_rules.

    `authorize(principal, scope)`:
      - searches rules where principal_id == principal.principal_id AND
        (scope == "*" OR scope == requested_scope);
      - returns the highest-priority rule's decision;
      - if no rule matches, returns DENY.
    """

    WILDCARD = "*"

    def __init__(self, substrate: Substrate) -> None:
        self._sub = substrate

    def add_rule(
        self,
        *,
        principal_id: str,
        scope: str,
        decision: AuthorityDecision,
        priority: int = 0,
    ) -> AuthorityRule:
        cursor = self._sub.connection.execute(
            "INSERT INTO harness_policy_rules"
            "(principal_id, scope, decision, priority, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (principal_id, scope, decision.value, priority, _utc_now_iso()),
        )
        self._sub.connection.commit()
        return AuthorityRule(
            rule_id=cursor.lastrowid or 0,
            principal_id=principal_id,
            scope=scope,
            decision=decision,
            priority=priority,
            created_at=_utc_now_iso(),
        )

    def list_rules(self, *, principal_id: str | None = None) -> list[AuthorityRule]:
        if principal_id is None:
            cursor = self._sub.connection.execute(
                "SELECT id, principal_id, scope, decision, priority, created_at "
                "FROM harness_policy_rules ORDER BY priority DESC, id ASC"
            )
        else:
            cursor = self._sub.connection.execute(
                "SELECT id, principal_id, scope, decision, priority, created_at "
                "FROM harness_policy_rules WHERE principal_id = ? "
                "ORDER BY priority DESC, id ASC",
                (principal_id,),
            )
        return [
            AuthorityRule(
                rule_id=row[0],
                principal_id=row[1],
                scope=row[2],
                decision=AuthorityDecision(row[3]),
                priority=row[4],
                created_at=row[5],
            )
            for row in cursor.fetchall()
        ]

    def remove_rule(self, rule_id: int) -> bool:
        cursor = self._sub.connection.execute(
            "DELETE FROM harness_policy_rules WHERE id = ?", (rule_id,)
        )
        self._sub.connection.commit()
        return cursor.rowcount > 0

    def authorize(self, principal: Principal, scope: str) -> AuthorityDecision:
        cursor = self._sub.connection.execute(
            "SELECT decision, priority FROM harness_policy_rules "
            "WHERE principal_id = ? AND (scope = ? OR scope = ?) "
            "ORDER BY priority DESC, id ASC LIMIT 1",
            (principal.principal_id, scope, self.WILDCARD),
        )
        row = cursor.fetchone()
        if row is None:
            return AuthorityDecision.DENY
        return AuthorityDecision(row[0])
