from __future__ import annotations

import pytest

from sonya.providers.pool import AccountPool


async def test_round_robin_rotation() -> None:
    pool = AccountPool(["key1", "key2", "key3"])
    k1 = await pool.get_key()
    k2 = await pool.get_key()
    k3 = await pool.get_key()
    k4 = await pool.get_key()
    assert k1 == "key1"
    assert k2 == "key2"
    assert k3 == "key3"
    assert k4 == "key1"  # wraps around


async def test_skips_rate_limited_key() -> None:
    pool = AccountPool(["key1", "key2"])
    await pool.mark_rate_limited("key1", retry_after_seconds=60)
    k = await pool.get_key()
    assert k == "key2"


async def test_rate_limit_expires() -> None:
    pool = AccountPool(["key1", "key2"])
    await pool.mark_rate_limited("key1", retry_after_seconds=0.01)
    import asyncio
    await asyncio.sleep(0.02)
    # After expiry, key1 should be available again
    k1 = await pool.get_key()
    k2 = await pool.get_key()
    keys = {k1, k2}
    assert "key1" in keys


async def test_all_limited_returns_least_limited() -> None:
    pool = AccountPool(["key1", "key2"])
    await pool.mark_rate_limited("key1", retry_after_seconds=100)
    await pool.mark_rate_limited("key2", retry_after_seconds=200)
    k = await pool.get_key()
    assert k == "key1"  # expires sooner


def test_empty_pool_raises() -> None:
    with pytest.raises(ValueError):
        AccountPool([])


def test_stats() -> None:
    pool = AccountPool(["sk-abc123", "sk-def456"])
    stats = pool.stats()
    assert len(stats) == 2
    assert stats[0]["key_prefix"] == "sk-abc12..."
