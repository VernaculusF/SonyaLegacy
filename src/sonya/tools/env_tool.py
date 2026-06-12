"""Environment tool — Sonya records what she observes about Ivan / context.

Examples:
    [TOOL: env.set ivan_status спит]
    [TOOL: env.set ivan_status работает над парсером]
    [TOOL: env.set mood уставший]
    [TOOL: env.get ivan_status]
    [TOOL: env.list]
    [TOOL: env.clear ivan_status]

Used to replace clock-based sleep heuristics. Sonya infers from what Ivan
says ("я лёг спать", "иду по делам", "буду занят пару часов") and records.
The OutboundGate respects ivan_status='спит'/'занят' and won't initiate.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from sonya.state.situational import SituationalStore
from sonya.state.substrate import Substrate


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class EnvTool:
    """Agent-facing wrapper around SituationalStore (legacy env tool)."""

    def __init__(self, substrate: Substrate) -> None:
        self._sub = substrate
        self._situational = SituationalStore(substrate)

    def set(self, arg: str) -> str:
        """Record a structured situational assertion."""
        if not arg or not arg.strip():
            return "[ERROR] env.set needs: <key> <value>"
        
        # Fast path for explicit JSON
        if arg.lstrip().startswith("{"):
            try:
                data = json.loads(arg)
                assertion = self._situational.assert_fact(
                    subject=str(data.get("subject", "ivan")).strip(),
                    predicate=str(data.get("predicate", "")).strip(),
                    value=str(data.get("value", "")),
                    source=str(data.get("source", "observation")),
                    source_ref=str(data.get("source_ref", "agent")),
                    confidence=float(data.get("confidence", 0.5)),
                    observed_at=str(data.get("observed_at", "")),
                    expires_at=str(data.get("expires_at", "")),
                    scope=str(data.get("scope", "global")),
                    visibility=str(data.get("visibility", "normal")),
                )
            except Exception as exc:
                return f"[ERROR] env.set failed: {exc}"
            return (
                f"[OK] env.set {assertion.subject}.{assertion.predicate}="
                f"{assertion.value!r} confidence={assertion.confidence:.2f}"
            )
            
        # Fallback for simple `<key> <value>`
        parts = arg.strip().split(None, 1)
        if len(parts) < 2:
            return "[ERROR] env.set needs: <key> <value>"
        
        # For legacy `env.set ivan_status спит` mapping
        # If predicate has "status", or key is "ivan_status", map to subject="ivan", predicate="status"
        key, value = parts[0], parts[1]
        
        subject = "ivan"
        predicate = key
        if key == "ivan_status":
            predicate = "status"

        # Auto-expiry TTL
        hours = 8 if value.lower() in ("спит", "сплю", "sleeping", "asleep") else 4
        expires_at = (_utc_now() + timedelta(hours=hours)).isoformat()

        try:
            assertion = self._situational.assert_fact(
                subject=subject,
                predicate=predicate,
                value=value,
                source="observation",
                expires_at=expires_at,
            )
        except Exception as exc:
            return f"[ERROR] env.set failed: {exc}"
            
        return f"[OK] env.set {subject}.{predicate}={assertion.value!r} (expires in {hours}h)"

    def get(self, key: str) -> str:
        key = key.strip()
        if not key:
            return "[ERROR] env.get needs a key"
        
        subject = "ivan"
        predicate = key
        if key == "ivan_status":
            predicate = "status"

        try:
            item = self._situational.get_current(subject=subject, predicate=predicate)
            if item is None:
                return f"(no active assertion for {subject}.{predicate})"
            return f"{subject}.{predicate}: {item.value} (source={item.source}, expires_at={item.expires_at[:19] if item.expires_at else 'none'})"
        except Exception as exc:
            return f"[ERROR] env.get failed: {exc}"

    def list_all(self) -> str:
        try:
            # We list all active assertions for subject "ivan"
            items = self._situational.list_current_for_subject("ivan")
            if not items:
                return "(no environment state recorded for ivan)"
            lines = ["Environment state (ivan):"]
            for v in items:
                lines.append(
                    f"- {v.predicate}: {v.value} "
                    f"(source={v.source}, expires_at={v.expires_at[:19] if v.expires_at else 'none'})"
                )
            return "\n".join(lines)
        except Exception as exc:
            return f"[ERROR] env.list_all failed: {exc}"

    def clear(self, key: str) -> str:
        key = key.strip()
        if not key:
            return "[ERROR] env.clear needs a key"
        
        subject = "ivan"
        predicate = key
        if key == "ivan_status":
            predicate = "status"

        try:
            invalidated = self._situational.invalidate_predicate(subject=subject, predicate=predicate, reason="agent_cleared")
            return f"[OK] env.clear {subject}.{predicate}" if invalidated else f"(no active assertion to clear for {subject}.{predicate})"
        except Exception as exc:
            return f"[ERROR] env.clear failed: {exc}"


__all__ = ["EnvTool"]
