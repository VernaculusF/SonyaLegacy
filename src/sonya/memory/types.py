from __future__ import annotations

from enum import Enum, unique
from dataclasses import dataclass, field
from typing import Any


@unique
class RecordType(str, Enum):
    raw_trace = "raw_trace"
    tool_observation = "tool_observation"
    subagent_trace = "subagent_trace"
    semantic_fact = "semantic_fact"
    operational_lesson = "operational_lesson"
    project_event = "project_event"
    identity_record = "identity_record"
    user_preference = "user_preference"
    model_score = "model_score"
    dialogue_event = "dialogue_event"
    initiative_event = "initiative_event"
    session_outcome = "session_outcome"
    idle_thought = "idle_thought"


@unique
class Scope(str, Enum):
    global_ = "global"
    main_chat = "main_chat"
    project = "project"
    subagent = "subagent"
    identity = "identity"


@unique
class RetentionPolicy(str, Enum):
    short = "short"
    medium = "medium"
    long = "long"
    archive_only = "archive_only"
    identity_critical = "identity_critical"


_DEFAULT_RETENTION: dict[RecordType, RetentionPolicy] = {
    RecordType.raw_trace: RetentionPolicy.archive_only,
    RecordType.tool_observation: RetentionPolicy.short,
    RecordType.subagent_trace: RetentionPolicy.archive_only,
    RecordType.semantic_fact: RetentionPolicy.long,
    RecordType.operational_lesson: RetentionPolicy.long,
    RecordType.project_event: RetentionPolicy.medium,
    RecordType.identity_record: RetentionPolicy.identity_critical,
    RecordType.user_preference: RetentionPolicy.long,
    RecordType.model_score: RetentionPolicy.medium,
    RecordType.dialogue_event: RetentionPolicy.medium,
    RecordType.initiative_event: RetentionPolicy.medium,
    RecordType.session_outcome: RetentionPolicy.medium,
    RecordType.idle_thought: RetentionPolicy.short,
}

_DEFAULT_SCOPE: dict[RecordType, Scope] = {
    RecordType.raw_trace: Scope.global_,
    RecordType.tool_observation: Scope.global_,
    RecordType.subagent_trace: Scope.subagent,
    RecordType.semantic_fact: Scope.global_,
    RecordType.operational_lesson: Scope.global_,
    RecordType.project_event: Scope.project,
    RecordType.identity_record: Scope.identity,
    RecordType.user_preference: Scope.global_,
    RecordType.model_score: Scope.global_,
    RecordType.dialogue_event: Scope.main_chat,
    RecordType.initiative_event: Scope.main_chat,
    RecordType.session_outcome: Scope.global_,
    RecordType.idle_thought: Scope.global_,
}

_TRACE_TYPES: frozenset[RecordType] = frozenset({
    RecordType.raw_trace,
    RecordType.tool_observation,
    RecordType.subagent_trace,
})

_BEHAVIOR_TYPES: frozenset[RecordType] = frozenset({
    RecordType.semantic_fact,
    RecordType.operational_lesson,
    RecordType.project_event,
    RecordType.identity_record,
    RecordType.user_preference,
    RecordType.model_score,
    RecordType.dialogue_event,
    RecordType.initiative_event,
    RecordType.session_outcome,
    RecordType.idle_thought,
})


def is_trace_type(rt: RecordType) -> bool:
    return rt in _TRACE_TYPES


def is_behavior_type(rt: RecordType) -> bool:
    return rt in _BEHAVIOR_TYPES


def default_retention(rt: RecordType) -> RetentionPolicy:
    return _DEFAULT_RETENTION.get(rt, RetentionPolicy.medium)


def default_scope(rt: RecordType) -> Scope:
    return _DEFAULT_SCOPE.get(rt, Scope.global_)


def classify_event_type(event_type: str) -> RecordType:
    mapping: dict[str, RecordType] = {
        "dialogue_event": RecordType.dialogue_event,
        "initiative_event": RecordType.initiative_event,
        "session_outcome": RecordType.session_outcome,
        "idle_thought": RecordType.idle_thought,
        "tool_event": RecordType.tool_observation,
    }
    return mapping.get(event_type, RecordType.raw_trace)


@dataclass(frozen=True, slots=True)
class MemoryRecordMeta:
    record_type: RecordType
    importance: float = 0.5
    scope: Scope = Scope.global_
    source: str = ""
    stability: float = 0.5
    project_id: str = ""
    retention_policy: RetentionPolicy = RetentionPolicy.medium

    @classmethod
    def for_type(
        cls,
        record_type: RecordType,
        *,
        importance: float | None = None,
        scope: Scope | None = None,
        source: str = "",
        stability: float | None = None,
        project_id: str = "",
        retention_policy: RetentionPolicy | None = None,
    ) -> MemoryRecordMeta:
        return cls(
            record_type=record_type,
            importance=importance if importance is not None else 0.5,
            scope=scope if scope is not None else default_scope(record_type),
            source=source,
            stability=stability if stability is not None else 0.5,
            project_id=project_id,
            retention_policy=retention_policy if retention_policy is not None else default_retention(record_type),
        )


__all__ = [
    "RecordType",
    "Scope",
    "RetentionPolicy",
    "MemoryRecordMeta",
    "is_trace_type",
    "is_behavior_type",
    "default_retention",
    "default_scope",
    "classify_event_type",
]