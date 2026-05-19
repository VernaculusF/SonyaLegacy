from __future__ import annotations

import json
from pathlib import Path

from sonya.state.substrate import Substrate
from sonya.state.continuity_stream import ContinuityStream
from sonya.state.subject_state import SubjectStateStore
from sonya.state.identity import IdentityWriter
from sonya.memory.episodic import EpisodicMemory
from sonya.memory.semantic import SemanticMemory
from sonya.state.pending import PendingIntentionStore


class SelfInspectTool:
    """Sonya can inspect her own substrate, code, and state."""

    def __init__(self, substrate: Substrate, project_root: Path | None = None) -> None:
        self._sub = substrate
        self._root = project_root or Path(__file__).resolve().parent.parent.parent.parent

    def read_identity(self) -> str:
        identity = IdentityWriter(self._sub).load()
        return json.dumps({
            "self_model": identity.self_model,
            "things_not_to_betray": list(identity.things_not_to_betray),
            "identity_critical_traits": list(identity.identity_critical_traits),
        }, ensure_ascii=False, indent=2)

    def read_subject_state(self) -> str:
        state = SubjectStateStore(self._sub).load()
        return json.dumps({
            "active_principal_id": state.active_principal_id,
            "emotional_vector": state.emotional_vector,
            "drift_signals": list(state.drift_signals),
            "pending_intentions": list(state.pending_intentions),
        }, ensure_ascii=False, indent=2)

    def read_recent_thoughts(self, limit: int = 10) -> str:
        stream = ContinuityStream(self._sub)
        latest = stream.latest_seq()
        events = list(stream.read_since(max(0, latest - 80)))
        thoughts = [e for e in events if "thought" in e.kind or "cognitive" in e.kind][-limit:]
        # Full thought text — these are her own memories. Truncating them at 200 chars
        # was the bug behind broken continuity (мысли обрывались на полуслове).
        return "\n---\n".join(
            f"[{e.kind} tick={e.payload.get('tick','')}] "
            f"{e.payload.get('thought') or e.payload.get('content') or json.dumps(e.payload, ensure_ascii=False)[:1500]}"
            for e in thoughts
        )

    def read_recent_memories(self, limit: int = 10) -> str:
        memories = EpisodicMemory(self._sub).get_recent(limit=limit)
        return "\n".join(
            f"[{m.event_type} {m.timestamp[:16]}] {m.raw_content[:600]}"
            for m in memories
        )

    def read_active_intentions(self) -> str:
        intentions = PendingIntentionStore(self._sub).list_active()
        if not intentions:
            return "No active intentions."
        return "\n".join(
            f"- {i.intention_id}: {i.description} (deadline: {i.deadline or 'none'})"
            for i in intentions
        )

    def read_own_code(self, module_path: str) -> str:
        """Read a source file from src/sonya/. If a directory is given,
        list its python files instead so the agent can pick a specific one."""
        full = self._root / "src" / "sonya" / module_path
        if not full.exists():
            return f"[ERROR] Module not found: {module_path}"
        if full.is_dir():
            entries = sorted(full.iterdir())
            files = [e.name for e in entries if e.is_file() and e.name.endswith(".py")]
            subdirs = [e.name + "/" for e in entries if e.is_dir() and not e.name.startswith("_")]
            lines = [f"{module_path}/ — directory listing:"]
            for d in subdirs:
                lines.append(f"  {d}")
            for f in files:
                lines.append(f"  {f}")
            lines.append("")
            lines.append("Pick one and call again, e.g. `[TOOL: self_inspect.code "
                         f"{module_path}/{files[0] if files else '<file>'}]`")
            return "\n".join(lines)
        return full.read_text(encoding="utf-8")[:8000]

    def list_own_modules(self) -> str:
        """List all packages in src/sonya/."""
        sonya_dir = self._root / "src" / "sonya"
        packages = [d.name for d in sorted(sonya_dir.iterdir()) if d.is_dir() and not d.name.startswith("_")]
        return "\n".join(packages)
