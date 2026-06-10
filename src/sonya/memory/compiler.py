from __future__ import annotations

import logging
from typing import Any

from sonya.memory.episodic import EpisodicMemory, EpisodicEvent
from sonya.memory.semantic import SemanticMemory
from sonya.memory.procedural import ProceduralMemory
from sonya.memory.trace_layer import TraceLayer, TraceEntry
from sonya.memory.types import (
    RecordType, Scope, RetentionPolicy,
    is_trace_type, is_behavior_type,
    classify_event_type,
)
from sonya.state.substrate import Substrate

_log = logging.getLogger("sonya.memory.compiler")


class MemoryCompiler:
    def __init__(
        self,
        substrate: Substrate,
        *,
        episodic: EpisodicMemory | None = None,
        semantic: SemanticMemory | None = None,
        procedural: ProceduralMemory | None = None,
        trace: TraceLayer | None = None,
    ) -> None:
        self._sub = substrate
        self._episodic = episodic or EpisodicMemory(substrate)
        self._semantic = semantic or SemanticMemory(substrate)
        self._procedural = procedural or ProceduralMemory(substrate)
        self._trace = trace or TraceLayer(substrate)

    def run(self, *, since_hours: int = 24) -> dict[str, int]:
        results = {
            "facts_created": 0,
            "lessons_created": 0,
            "project_summaries": 0,
            "subagent_summaries": 0,
            "archived_traces": 0,
        }

        results["facts_created"] = self._compile_semantic_facts(since_hours=since_hours)
        results["lessons_created"] = self._compile_procedural_lessons(since_hours=since_hours)
        results["project_summaries"] = self._compile_project_summaries(since_hours=since_hours)
        results["subagent_summaries"] = self._compile_subagent_summaries(since_hours=since_hours)
        results["archived_traces"] = self._trace.apply_decay(archive_after_days=30)

        self._semantic.apply_decay()
        self._episodic.apply_decay()

        return results

    def _compile_semantic_facts(self, *, since_hours: int = 24) -> int:
        events = self._episodic.get_recent(limit=500, mark_accessed=False)
        existing = {f.statement.strip().lower() for f in self._semantic.get_all(limit=1000)}

        created = 0
        for ev in events:
            rt = classify_event_type(ev.event_type)
            if is_trace_type(rt):
                continue
            if ev.importance_score < 0.5:
                continue
            summary = (ev.normalized_summary or "").strip()
            if not summary or len(summary) < 15:
                continue
            if summary.lower() in existing:
                continue

            scope = Scope.main_chat if rt in (
                RecordType.dialogue_event, RecordType.initiative_event,
            ) else Scope.global_

            project_id = ""
            if ev.channel and ev.channel.startswith("project_"):
                project_id = ev.channel.replace("project_", "", 1)

            self._semantic.add_fact(
                fact_type="consolidated_observation",
                statement=summary,
                source_event_ids=(ev.event_id,),
                confidence=min(1.0, ev.importance_score + 0.1),
            )
            existing.add(summary.lower())
            created += 1
            if created >= 50:
                break

        traces = self._trace.get_for_compilation(since_hours=since_hours, limit=200)
        for t in traces:
            if t.importance < 0.5:
                continue
            summary = (t.normalized_summary or "").strip()
            if not summary or len(summary) < 15:
                continue
            if summary.lower() in existing:
                continue

            self._semantic.add_fact(
                fact_type="trace_compiled_fact",
                statement=summary,
                source_event_ids=(t.trace_id,),
                confidence=min(1.0, t.importance + 0.1),
            )
            existing.add(summary.lower())
            created += 1
            if created >= 50:
                break

        return created

    def _compile_procedural_lessons(self, *, since_hours: int = 24) -> int:
        existing = {l.statement.strip().lower() for l in self._procedural.get_all(limit=500)}
        created = 0

        traces = self._trace.get_by_type(RecordType.tool_observation, limit=200)
        for t in traces:
            content = (t.raw_content or "").strip()
            if not content:
                continue
            outcome = "error" if "[ERROR]" in content[:20] else "success"
            if outcome == "success":
                lesson = f"{t.tags[0] if t.tags else 'tool'}: {t.source} works reliably"
            else:
                lesson = f"{t.tags[0] if t.tags else 'tool'}: {t.source} fails — {content[:80]}"
            if lesson.lower() in existing:
                continue
            if len(lesson) < 15:
                continue

            self._procedural.add_lesson(
                statement=lesson,
                domain="tool_usage",
                pattern=t.session_type,
                project_id=t.project_id,
                source_trace_ids=(t.trace_id,),
                confidence=0.6 if outcome == "success" else 0.7,
                scope=Scope.subagent if t.session_type == "subagent" else Scope.global_,
            )
            existing.add(lesson.lower())
            created += 1
            if created >= 30:
                break

        tool_errors = self._get_recent_tool_errors(since_hours=since_hours)
        for tool_name, detail in tool_errors:
            lesson = f"Avoid {tool_name} in certain scenarios — {detail[:80]}"
            if lesson.lower() in existing:
                continue
            self._procedural.add_lesson(
                statement=lesson,
                domain="tool_failure",
                pattern=tool_name,
                source_trace_ids=(),
                confidence=0.75,
            )
            existing.add(lesson.lower())
            created += 1
            if created >= 30:
                break

        return created

    def _compile_project_summaries(self, *, since_hours: int = 24) -> int:
        created = 0
        try:
            from sonya.project import ProjectStore, ProjectRunStore
            projects = ProjectStore(self._sub).list_all()
            for p in projects:
                if p.status not in ("in_progress", "active"):
                    continue
                runs = ProjectRunStore(self._sub).list_by_project(p.project_id, limit=3)
                recent_completed = [r for r in runs if r.status in ("completed", "failed")]
                if not recent_completed:
                    continue
                last = recent_completed[0]
                summary = (
                    f"Project {p.title}: last run {last.kind} "
                    f"{last.status} — {last.result[:100] if last.result else 'no result'}"
                )
                existing = {f.statement.strip().lower() for f in self._semantic.get_all(limit=1000)}
                if summary.lower() in existing:
                    continue

                self._semantic.add_fact(
                    fact_type="project_summary",
                    statement=summary,
                    source_event_ids=(),
                    confidence=0.6,
                )
                created += 1
                if created >= 20:
                    break
        except Exception:
            pass
        return created

    def _compile_subagent_summaries(self, *, since_hours: int = 24) -> int:
        created = 0
        try:
            rows = self._sub.connection.execute(
                "SELECT subagent_id, task, status, result, steps_taken "
                "FROM subagent_tasks "
                "WHERE status IN ('done', 'failed') "
                "AND completed_at > datetime('now', ?) "
                "ORDER BY completed_at DESC LIMIT 20",
                (f"-{since_hours} hours",),
            ).fetchall()
            existing = {f.statement.strip().lower() for f in self._semantic.get_all(limit=1000)}
            for sub_id, task, status, result, steps in rows:
                task_brief = (task or "")[:100]
                result_brief = (result or "")[:100]
                summary = f"Subagent {sub_id}: {task_brief} → {status} ({steps} steps) — {result_brief}"
                if summary.lower() in existing:
                    continue

                self._semantic.add_fact(
                    fact_type="subagent_summary",
                    statement=summary,
                    source_event_ids=(),
                    confidence=0.65 if status == "done" else 0.75,
                )
                created += 1
                if created >= 20:
                    break
        except Exception:
            pass
        return created

    def _get_recent_tool_errors(self, *, since_hours: int = 24) -> list[tuple[str, str]]:
        try:
            from datetime import timedelta
            from sonya.memory.tool_experience import ToolExperience
            errors = ToolExperience(self._sub).recent_errors(limit=30)
            return [(e.tool_name, e.outcome_detail[:80]) for e in errors]
        except Exception:
            return []


__all__ = ["MemoryCompiler"]