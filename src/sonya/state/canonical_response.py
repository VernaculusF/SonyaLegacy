from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class ResponseKind(str, Enum):
    """All canonical response kinds.

    Kinds cover both external-facing responses (reply, clarification, etc.)
    and internal subject events (self_observation, internal_reflection).
    """

    REPLY = "reply"
    TASK_CREATED = "task_created"
    TASK_UPDATE = "task_update"
    TASK_RESULT = "task_result"
    IMAGE_GENERATED = "image_generated"
    CLARIFICATION = "clarification"
    LIMITATION = "limitation"
    SILENCE = "silence"
    INITIATIVE_PROPOSAL = "initiative_proposal"
    SELF_OBSERVATION = "self_observation"
    INTERNAL_REFLECTION = "internal_reflection"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True, slots=True)
class CanonicalResponse:
    """Channel-independent response object.

    Produced by planner (Phase 7) or internal loop before any channel-specific
    rendering. Bridge and future channels consume this through public API.

    See: docs/cognition/CONTINUITY_STREAM_AND_SUBJECT_CORE.md §6.3.
    """

    kind: ResponseKind
    text: str = ""
    principal_id: str | None = None
    task_ref: str = ""
    attachments: tuple[str, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_utc_now_iso)
