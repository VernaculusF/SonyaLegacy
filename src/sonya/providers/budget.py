"""Daily budget cap for LLM requests.

Prevents runaway spending from thinking loop or crash-restart cycles.
"""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass(slots=True)
class DailyBudget:
    """Track and limit daily LLM requests."""

    max_requests_per_day: int = 200
    _count: int = 0
    _day_start: float = 0.0

    def __post_init__(self):
        self._day_start = time.time()

    def can_request(self) -> bool:
        """Check if we're within budget."""
        self._maybe_reset_day()
        return self._count < self.max_requests_per_day

    def record_request(self) -> None:
        """Record one LLM request."""
        self._maybe_reset_day()
        self._count += 1

    def _maybe_reset_day(self) -> None:
        """Reset counter if 24h passed."""
        if time.time() - self._day_start > 86400:
            self._count = 0
            self._day_start = time.time()

    @property
    def remaining(self) -> int:
        self._maybe_reset_day()
        return max(0, self.max_requests_per_day - self._count)

    @property
    def used_today(self) -> int:
        self._maybe_reset_day()
        return self._count
