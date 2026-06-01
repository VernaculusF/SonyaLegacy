"""Tests for KeyStore.acquire — key acquisition (slot-less, 2026-06-02).

Background: prior to 2026-06-02, KeyStore.acquire() and acquire_strict()
filtered keys by slot. Per Ivan's directive, all keys are now slot=text
and the slot parameter has been removed. acquire(provider) picks the
highest-priority eligible key for the given provider.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from sonya.providers.keystore import KeyStore, ProviderKey, KeyStatus
from sonya.state.substrate import Substrate


@pytest.fixture
def store(tmp_path):
    sub = Substrate.open(tmp_path / "s.db")
    ks = KeyStore(sub)
    yield ks
    sub.close()


def _seed(store: KeyStore, provider: str, key: str, *, priority: int = 0, model: str = "") -> None:
    """Insert one key with the given provider/model."""
    store.add_key(
        provider=provider,
        api_key=key,
        name=f"{provider}-{key}",
        model=model,
        base_url="",
        slot="text",
        priority=priority,
    )


def test_acquire_returns_none_when_no_keys(store: KeyStore) -> None:
    out = asyncio.run(store.acquire("fireworks"))
    assert out is None


def test_acquire_picks_highest_priority(store: KeyStore) -> None:
    _seed(store, "kr", "kr-1", priority=1, model="sonnet")
    _seed(store, "kr", "kr-2", priority=5, model="haiku")
    out = asyncio.run(store.acquire("kr"))
    assert out is not None
    assert out.model == "haiku"  # priority 5 wins over priority 1
    assert out.name == "kr-kr-2"


def test_acquire_filters_by_provider(store: KeyStore) -> None:
    _seed(store, "fireworks", "fw-1", model="pro")
    _seed(store, "kr", "kr-1", model="haiku")
    out = asyncio.run(store.acquire("kr"))
    assert out is not None
    assert out.provider == "kr"
    assert out.model == "haiku"


def test_acquire_skips_banned(store: KeyStore) -> None:
    _seed(store, "kr", "kr-1", model="haiku")
    raw = store.list_keys("kr")[0]
    store.update_status(raw.key_id, KeyStatus.BANNED)
    out = asyncio.run(store.acquire("kr"))
    assert out is None  # no eligible keys


def test_acquire_strict_is_same_as_acquire(store: KeyStore) -> None:
    """acquire_strict(provider) now delegates to acquire(provider) since
    all keys are slot=text."""
    _seed(store, "fireworks", "fw-1", model="pro")
    a = asyncio.run(store.acquire("fireworks"))
    b = asyncio.run(store.acquire_strict("fireworks"))
    assert a is not None and b is not None
    assert a.key_id == b.key_id


def test_acquire_by_slot_still_works_for_vision_etc(store: KeyStore) -> None:
    """acquire_by_slot(slot) — still functional for non-text slots
    (vision, embedding, etc.)."""
    _seed(store, "fireworks", "fw-vision", model="vision-pro")
    # Override slot to "vision" since we're testing by_slot behavior
    raw = store.list_keys("fireworks")[0]
    store._sub.connection.execute("UPDATE provider_keys SET slot = 'vision' WHERE key_id = ?", (raw.key_id,))
    store._sub.connection.commit()
    out = asyncio.run(store.acquire_by_slot("vision"))
    assert out is not None
    assert out.model == "vision-pro"

    out2 = asyncio.run(store.acquire_by_slot("text"))
    assert out2 is None  # only vision key exists
