from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class ScheduledJob:
    """A scheduled job in the hyper-harness scheduler shell.

    Stub — real scheduler with risk-tiered concurrency is post-MVP Track F.
    See: SYSTEM_CORE §7.13.
    """

    job_id: str
    job_type: str  # consolidation, drift_check, skill_eval
    priority: int = 0
    status: str = "pending"  # pending, running, completed, failed, cancelled
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SupervisionPolicy:
    """Supervision policy stub for concurrent task branches.

    Stub — real isolation and cancellation logic is post-MVP Track F.
    """

    max_concurrent: int = 3
    timeout_seconds: int = 300
    risk_tier: str = "low"  # low, medium, high, critical
