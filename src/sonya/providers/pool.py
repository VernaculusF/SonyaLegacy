from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field


@dataclass(slots=True)
class AccountKey:
    """One OpenRouter API key with rate limit tracking."""

    key: str
    last_used: float = 0.0
    daily_count: int = 0
    last_reset_day: int = 0
    is_rate_limited: bool = False
    rate_limit_until: float = 0.0


class AccountPool:
    """Round-robin pool of OpenRouter API keys for rate limit avoidance.

    Each key with $10+ credits gets 1000 req/day, 20 req/min on free models.
    Pool rotates keys to distribute load. On 429 — marks key as rate-limited
    and switches to next.

    See: INTERIM_CRUTCHES.md CRUTCH-009.
    """

    def __init__(self, keys: list[str]) -> None:
        if not keys:
            raise ValueError("AccountPool requires at least one API key")
        self._accounts = [AccountKey(key=k) for k in keys]
        self._index = 0
        self._lock = asyncio.Lock()

    @property
    def size(self) -> int:
        return len(self._accounts)

    async def get_key(self) -> str:
        """Get next available API key (round-robin, skip rate-limited)."""
        async with self._lock:
            now = time.time()
            attempts = 0
            while attempts < len(self._accounts):
                account = self._accounts[self._index]
                self._index = (self._index + 1) % len(self._accounts)

                # Check if rate limit expired
                if account.is_rate_limited and now > account.rate_limit_until:
                    account.is_rate_limited = False

                if not account.is_rate_limited:
                    account.last_used = now
                    account.daily_count += 1
                    return account.key

                attempts += 1

            # All keys rate-limited — return least-recently-limited one
            best = min(self._accounts, key=lambda a: a.rate_limit_until)
            best.is_rate_limited = False
            best.last_used = now
            return best.key

    async def mark_rate_limited(self, key: str, retry_after_seconds: float = 60.0) -> None:
        """Mark a key as rate-limited after receiving 429."""
        async with self._lock:
            for account in self._accounts:
                if account.key == key:
                    account.is_rate_limited = True
                    account.rate_limit_until = time.time() + retry_after_seconds
                    break

    def stats(self) -> list[dict]:
        """Return usage stats for all keys."""
        return [
            {
                "key_prefix": a.key[:8] + "...",
                "daily_count": a.daily_count,
                "is_rate_limited": a.is_rate_limited,
            }
            for a in self._accounts
        ]
