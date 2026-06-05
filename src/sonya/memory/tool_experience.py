from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sonya.state.substrate import Substrate


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class ToolExperienceEntry:
    exp_id: str
    tool_name: str
    tool_arg_summary: str
    outcome: str
    outcome_detail: str
    provider: str
    model: str
    latency_ms: int
    tags: tuple[str, ...] = field(default_factory=tuple)
    session_type: str = ""
    created_at: str = ""


class ToolExperience:
    """Records and queries tool invocation outcomes.

    Every call writes:
      1. A row in ``tool_experiences`` for fast aggregate queries.
      2. An ``episodic_events`` entry (event_type=``tool_event``) so
         Sonya can semantic-recall past tool experience via
         ``memory.recall "subagent.spawn"`` etc.

    The picker queries aggregate stats from tool_experiences.
    Sonya's reasoning layer queries episodic for nuanced recall.
    """

    _OUTCOMES = ("success", "error", "blocked", "timeout", "partial")

    def __init__(self, substrate: Substrate) -> None:
        self._sub = substrate

    def record(
        self,
        *,
        tool_name: str,
        tool_arg_summary: str = "",
        outcome: str = "success",
        outcome_detail: str = "",
        provider: str = "",
        model: str = "",
        latency_ms: int = 0,
        tags: tuple[str, ...] = (),
        session_type: str = "",
    ) -> ToolExperienceEntry:
        outcome = outcome if outcome in self._OUTCOMES else "success"
        exp_id = f"tx-{uuid4().hex[:12]}"
        now = _utc_now_iso()

        arg_summary = (tool_arg_summary or "")[:500]
        detail = (outcome_detail or "")[:1000]

        self._sub.connection.execute(
            "INSERT INTO tool_experiences"
            "(exp_id, tool_name, tool_arg_summary, outcome, outcome_detail, "
            "provider, model, latency_ms, tags_json, session_type, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (exp_id, tool_name, arg_summary, outcome, detail,
             provider, model, latency_ms,
             json.dumps(list(tags), ensure_ascii=False),
             session_type, now),
        )
        self._sub.connection.commit()

        mirror_summary = (
            f"[{tool_name}] {outcome}"
            + (f" — {detail[:120]}" if detail else "")
            + (f" | provider={provider}" if provider else "")
            + (f" model={model}" if model else "")
            + (f" latency={latency_ms}ms" if latency_ms else "")
        )
        mirror_raw = (
            f"Tool: {tool_name}\n"
            f"Arg: {arg_summary}\n"
            f"Outcome: {outcome}\n"
            f"Detail: {detail}\n"
            f"Provider: {provider}\n"
            f"Model: {model}\n"
            f"Latency: {latency_ms}ms\n"
            f"Session: {session_type}"
        )
        try:
            from sonya.memory.episodic import EpisodicMemory
            EpisodicMemory(self._sub).record(
                event_type="tool_event",
                raw_content=mirror_raw,
                normalized_summary=mirror_summary,
                source="sonya",
                channel="tool_experience",
                actor="sonya",
                emotion_tags=tags,
                importance_score=0.6 if outcome == "success" else 0.75,
            )
        except Exception:
            pass

        return ToolExperienceEntry(
            exp_id=exp_id, tool_name=tool_name,
            tool_arg_summary=arg_summary, outcome=outcome,
            outcome_detail=detail, provider=provider, model=model,
            latency_ms=latency_ms, tags=tags,
            session_type=session_type, created_at=now,
        )

    def success_rate(
        self,
        tool_name: str = "",
        provider: str = "",
        model: str = "",
        since_hours: int = 168,
    ) -> dict[str, Any]:
        """Aggregate success rate for a tool / provider / model.

        Returns dict with keys: total, success, error, blocked, timeout,
        partial, rate (0.0-1.0), avg_latency_ms.
        """
        clauses: list[str] = []
        params: list[Any] = []

        if tool_name:
            clauses.append("tool_name = ?")
            params.append(tool_name)
        if provider:
            clauses.append("provider = ?")
            params.append(provider)
        if model:
            clauses.append("model = ?")
            params.append(model)
        if since_hours > 0:
            from datetime import timedelta
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=since_hours)).isoformat()
            clauses.append("created_at >= ?")
            params.append(cutoff)

        where = " AND ".join(clauses) if clauses else "1=1"

        row = self._sub.connection.execute(
            f"SELECT outcome, COUNT(*), AVG(latency_ms) "
            f"FROM tool_experiences WHERE {where} "
            f"GROUP BY outcome",
            params,
        ).fetchall()

        counts: dict[str, int] = {"success": 0, "error": 0, "blocked": 0, "timeout": 0, "partial": 0}
        total = 0
        weighted_latency = 0.0

        for outcome_str, cnt, avg_lat in row:
            if outcome_str in counts:
                counts[outcome_str] = cnt
            total += cnt
            weighted_latency += (avg_lat or 0) * cnt

        avg_latency = int(weighted_latency / total) if total else 0
        rate = counts["success"] / total if total else 0.0

        return {
            "total": total,
            **counts,
            "rate": rate,
            "avg_latency_ms": avg_latency,
        }

    def recent_errors(
        self,
        tool_name: str = "",
        provider: str = "",
        limit: int = 10,
    ) -> list[ToolExperienceEntry]:
        clauses = ["outcome != 'success'"]
        params: list[Any] = []
        if tool_name:
            clauses.append("tool_name = ?")
            params.append(tool_name)
        if provider:
            clauses.append("provider = ?")
            params.append(provider)
        where = " AND ".join(clauses)

        rows = self._sub.connection.execute(
            f"SELECT exp_id, tool_name, tool_arg_summary, outcome, outcome_detail, "
            f"provider, model, latency_ms, tags_json, session_type, created_at "
            f"FROM tool_experiences WHERE {where} "
            f"ORDER BY created_at DESC LIMIT ?",
            (*params, limit),
        ).fetchall()
        return [_row_to_entry(r) for r in rows]

    def model_stats(self, provider: str = "", since_hours: int = 168) -> list[dict[str, Any]]:
        """Per-model aggregate stats. Used by picker to prefer models with
        higher success rates and avoid those with recent failures."""
        clauses: list[str] = []
        params: list[Any] = []
        if provider:
            clauses.append("provider = ?")
            params.append(provider)
        if since_hours > 0:
            from datetime import timedelta
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=since_hours)).isoformat()
            clauses.append("created_at >= ?")
            params.append(cutoff)
        where = " AND ".join(clauses) if clauses else "1=1"

        rows = self._sub.connection.execute(
            f"SELECT provider, model, "
            f"COUNT(*) as total, "
            f"SUM(CASE WHEN outcome='success' THEN 1 ELSE 0 END) as success, "
            f"SUM(CASE WHEN outcome='error' THEN 1 ELSE 0 END) as errors, "
            f"AVG(latency_ms) as avg_latency "
            f"FROM tool_experiences WHERE {where} "
            f"GROUP BY provider, model "
            f"ORDER BY total DESC",
            params,
        ).fetchall()

        result = []
        for provider_val, model_val, total, success, errors, avg_lat in rows:
            result.append({
                "provider": provider_val,
                "model": model_val,
                "total": total,
                "success": success,
                "errors": errors,
                "rate": success / total if total else 0.0,
                "avg_latency_ms": int(avg_lat or 0),
            })
        return result

    def recent_for_tool(self, tool_name: str, limit: int = 20) -> list[ToolExperienceEntry]:
        rows = self._sub.connection.execute(
            "SELECT exp_id, tool_name, tool_arg_summary, outcome, outcome_detail, "
            "provider, model, latency_ms, tags_json, session_type, created_at "
            "FROM tool_experiences WHERE tool_name = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (tool_name, limit),
        ).fetchall()
        return [_row_to_entry(r) for r in rows]


def _row_to_entry(row) -> ToolExperienceEntry:
    raw_tags = row[8] or "[]"
    try:
        tags = tuple(json.loads(raw_tags))
    except (json.JSONDecodeError, TypeError):
        tags = ()
    return ToolExperienceEntry(
        exp_id=row[0], tool_name=row[1], tool_arg_summary=row[2],
        outcome=row[3], outcome_detail=row[4], provider=row[5],
        model=row[6], latency_ms=row[7], tags=tags,
        session_type=row[9], created_at=row[10],
    )


def classify_outcome(observation: str) -> str:
    """Heuristic: classify tool observation string into an outcome label."""
    head = (observation or "").lstrip()[:20].upper()
    if head.startswith("[ERROR]"):
        return "error"
    if head.startswith("[BLOCKED]"):
        return "blocked"
    if head.startswith("[TIMEOUT]"):
        return "timeout"
    if head.startswith("[MAX_STEPS]"):
        return "partial"
    if head.startswith("[OK]"):
        return "success"
    if head.startswith("[SKIP]"):
        return "partial"
    return "success"


def extract_tool_tags(tool_name: str, arg: str, observation: str) -> tuple[str, ...]:
    """Derive descriptive tags from a tool call for later recall."""
    tags = [tool_name]
    family = tool_name.split(".")[0] if "." in tool_name else tool_name
    tags.append(f"tool_family:{family}")

    head = (observation or "").lstrip()[:20].upper()
    if head.startswith("[ERROR]"):
        tags.append("failed")
    elif head.startswith("[OK]"):
        tags.append("succeeded")

    if "subagent" in tool_name:
        tags.append("subagent")
    if "memory" in tool_name:
        tags.append("memory")
    if "web" in tool_name:
        tags.append("web")
    if "code" in tool_name or "shell" in tool_name:
        tags.append("code_execution")
    if "provider" in tool_name:
        tags.append("provider_mgmt")

    return tuple(tags)
