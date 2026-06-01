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

    def read_recent_memories(self, limit: int = 100, *, since: str = "", until: str = "") -> str:
        """Read episodic memories. Default: 100 most recent spanning ~2-3 days.

        Pass ``since`` / ``until`` ISO dates (e.g. ``since=2026-05-01``
        ``until=2026-06-01``) to zoom into a specific month. Without date
        args, returns the last ``limit`` events sorted by recency.

        For semantic search over ALL memories (embeddings-based), use
        ``memory.recall <query>`` — that tool searches the full corpus by
        meaning, not just recency.
        """
        ep = EpisodicMemory(self._sub)
        if since or until:
            memories = ep.get_by_date_range(since=since, until=until, limit=limit)
        else:
            memories = ep.get_recent(limit=limit)
        if not memories:
            return "(no memories found)"
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

    def read_drift_summary(self, days: int = 3) -> str:
        """Return aggregate self-observation: drift detector hit counts +
        blocked tasks + selfmod activity over the last ``days`` days.

        This is what powers the periodic self-improvement track. Sonya
        sees her OWN behaviour patterns (not Ivan judging her), decides
        which patterns to fix in her OWN code via selfmod.

        Output is plain text, not JSON, because it goes into ``initial_thought``
        seed of an active session — model reads it as a directive, not a
        structured response to parse.
        """
        import json as _json
        from datetime import datetime, timezone, timedelta

        cutoff_iso = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        conn = self._sub.connection

        # 1. Detector warning counts. We can't count log warnings directly
        #    from substrate (they go to journalctl), but the equivalent
        #    in-substrate signals are the events the detectors check on:
        #    initiative_blocked, task_worker_stuck_blocked, agent_session
        #    outcomes, etc.
        signals: list[tuple[str, str]] = []

        rows = conn.execute(
            "SELECT json_extract(payload_json, '$.reason') AS reason, COUNT(*) "
            "FROM continuity_events "
            "WHERE kind = 'internal.initiative_blocked' "
            "  AND created_at > ? "
            "GROUP BY reason ORDER BY COUNT(*) DESC LIMIT 6",
            (cutoff_iso,),
        ).fetchall()
        if rows:
            signals.append(("Мои попытки написать первой которые gate отклонил:",
                            "\n".join(f"  {n}× {(r or '(no reason)')[:120]}" for r, n in rows)))

        n_stuck = conn.execute(
            "SELECT COUNT(*) FROM continuity_events "
            "WHERE kind = 'internal.task_worker_stuck_blocked' "
            "  AND created_at > ?",
            (cutoff_iso,),
        ).fetchone()[0]
        if n_stuck:
            signals.append(("Stuck-loop блоки worker'а:",
                            f"  {n_stuck}× — задачи где я писала одно и то же 3+ хэндофа подряд"))

        # 2. Blocked / failed tasks
        rows = conn.execute(
            "SELECT task_id, status, sessions_used, title, blocker "
            "FROM tasks WHERE status IN ('blocked', 'failed') "
            "  AND updated_at > ? "
            "ORDER BY updated_at DESC LIMIT 8",
            (cutoff_iso,),
        ).fetchall()
        if rows:
            block_block = []
            for tid, st, used, title, blocker in rows:
                line = f"  [{st:7s}] {used} sess  {tid}  {(title or '')[:60]}"
                if blocker:
                    line += f"\n             blocker: {(blocker or '')[:140]}"
                block_block.append(line)
            signals.append(
                (f"Задачи в blocked/failed за последние {days} дней:",
                 "\n".join(block_block)))

        # 3. Selfmod activity
        n_proposals = conn.execute(
            "SELECT COUNT(*) FROM self_mod_proposals WHERE created_at > ?",
            (cutoff_iso,),
        ).fetchone()[0]
        n_applied = conn.execute(
            "SELECT COUNT(*) FROM continuity_events "
            "WHERE kind = 'self_mod.applied' AND created_at > ?",
            (cutoff_iso,),
        ).fetchone()[0]
        last_applied_row = conn.execute(
            "SELECT created_at, json_extract(payload_json, '$.target_module') "
            "FROM continuity_events "
            "WHERE kind = 'self_mod.applied' "
            "ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        sm_lines = [f"  proposals created: {n_proposals}", f"  applied: {n_applied}"]
        if last_applied_row:
            sm_lines.append(f"  last apply: {last_applied_row[0][:19]} → {last_applied_row[1]}")
        else:
            sm_lines.append("  last apply: NEVER")
        signals.append(("Selfmod активность:", "\n".join(sm_lines)))

        # 4. Active session counts (for context)
        n_active = conn.execute(
            "SELECT COUNT(*) FROM continuity_events "
            "WHERE kind = 'internal.agent_session_outcome' "
            "  AND created_at > ?",
            (cutoff_iso,),
        ).fetchone()[0]
        n_worker = conn.execute(
            "SELECT COUNT(*) FROM continuity_events "
            "WHERE kind = 'internal.task_worker_outcome' "
            "  AND created_at > ?",
            (cutoff_iso,),
        ).fetchone()[0]
        signals.append(
            ("Объём работы:",
             f"  active sessions: {n_active}\n  worker ticks: {n_worker}"))

        if not signals:
            return f"(чисто за {days} дней — ни одного дрейф-сигнала)"

        out = [f"## Drift summary за последние {days} дней", ""]
        for header, body in signals:
            out.append(header)
            out.append(body)
            out.append("")
        return "\n".join(out)
