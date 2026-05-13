from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class CanonicalResponse:
    kind: str
    text: str = ""
    task_ref: str = ""
    attachments: tuple[str, ...] = field(default_factory=tuple)
