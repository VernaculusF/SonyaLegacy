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

from sonya.state.environment import EnvironmentStore
from sonya.state.substrate import Substrate


class EnvTool:
    """Agent-facing wrapper around EnvironmentStore."""

    def __init__(self, substrate: Substrate) -> None:
        self._sub = substrate
        self._store = EnvironmentStore(substrate)

    def set(self, arg: str) -> str:
        """`env.set <key> <value>` — record an observation."""
        if not arg or not arg.strip():
            return "[ERROR] env.set needs: <key> <value>"
        parts = arg.strip().split(None, 1)
        if len(parts) < 2:
            return "[ERROR] env.set needs: <key> <value>"
        key, value = parts[0], parts[1]
        try:
            self._store.set(key, value, source="observation", updated_by="agent")
        except Exception as exc:
            return f"[ERROR] env.set failed: {exc}"
        return f"[OK] env.set {key}={value!r}"

    def get(self, key: str) -> str:
        key = key.strip()
        if not key:
            return "[ERROR] env.get needs a key"
        item = self._store.get(key)
        if item is None:
            return f"(no env value for {key!r})"
        return f"{key}: {item['value']} (source={item['source']}, updated_at={item['updated_at'][:19]})"

    def list_all(self) -> str:
        items = self._store.list_all()
        if not items:
            return "(no environment state recorded)"
        lines = ["Environment state:"]
        for k, v in items.items():
            lines.append(
                f"- {k}: {v['value']} "
                f"(source={v['source']}, at={v['updated_at'][:19]})"
            )
        return "\n".join(lines)

    def clear(self, key: str) -> str:
        key = key.strip()
        if not key:
            return "[ERROR] env.clear needs a key"
        ok = self._store.clear(key)
        return f"[OK] env.clear {key}" if ok else f"(no env value to clear for {key!r})"


__all__ = ["EnvTool"]
