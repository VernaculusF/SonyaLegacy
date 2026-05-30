"""Tests for KeyStore.acquire_strict — slot-precise key acquisition.

Background: prior to 2026-05-30 KeyStore.acquire() softly fell back to any
eligible key when no slot match existed. That defeated per-purpose routing
because the LLM provider would happily land on a deep-slot key for a
fast-slot request and use the deep model. acquire_strict() is the new
slot-precise primitive used in phase 1 of LLMProvider.complete_text.
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


def _seed(store: KeyStore, provider: str, key: str, *, slot: str, model: str = "") -> None:
    """Insert one key with the given provider/slot/model."""
    store.add_key(
        provider=provider,
        api_key=key,
        name=f"{provider}-{slot.replace(',', '-')}",
        model=model,
        base_url="",
        slot=slot,
    )


def test_acquire_strict_returns_none_when_slot_missing(store: KeyStore) -> None:
    _seed(store, "fireworks", "fw-deep-1", slot="text-deep,text", model="m-pro")
    out = asyncio.run(store.acquire_strict("fireworks", slot="text-fast"))
    assert out is None, "strict acquire must NOT fall back to a non-matching slot"


def test_acquire_strict_returns_match(store: KeyStore) -> None:
    _seed(store, "kr", "kr-fast-1", slot="text-fast,text", model="haiku")
    out = asyncio.run(store.acquire_strict("kr", slot="text-fast"))
    assert out is not None
    assert out.model == "haiku"


def test_acquire_strict_prefers_higher_priority(store: KeyStore) -> None:
    _seed(store, "kr", "kr-A", slot="text-fast", model="A")
    _seed(store, "kr", "kr-B", slot="text-fast", model="B")
    # Bump B's priority; should win.
    store._sub.connection.execute(
        "UPDATE provider_keys SET priority = 10 WHERE name = ?",
        ("kr-text-fast",),
    )
    store._sub.connection.commit()
    # Both have name=kr-text-fast — that's fine, just pick whichever has
    # higher priority. Set the second one we inserted (api_key='kr-B').
    store._sub.connection.execute(
        "UPDATE provider_keys SET priority = 10 WHERE api_key = 'kr-B'"
    )
    store._sub.connection.execute(
        "UPDATE provider_keys SET priority = 0 WHERE api_key = 'kr-A'"
    )
    store._sub.connection.commit()
    out = asyncio.run(store.acquire_strict("kr", slot="text-fast"))
    assert out is not None
    assert out.model == "B"


def test_acquire_strict_skips_disabled(store: KeyStore) -> None:
    _seed(store, "kr", "kr-1", slot="text-fast")
    # Disable directly via update_status
    keys = store.list_keys("kr")
    assert keys, "seed didn't insert"
    store.update_status(keys[0].key_id, KeyStatus.DISABLED)
    out = asyncio.run(store.acquire_strict("kr", slot="text-fast"))
    assert out is None


def test_acquire_softfallback_still_works(store: KeyStore) -> None:
    """Sanity: relaxed acquire() still falls back to any text key when
    the requested slot is empty (legacy behaviour preserved)."""
    _seed(store, "fireworks", "fw-deep", slot="text-deep,text", model="pro")
    out = asyncio.run(store.acquire("fireworks", slot="text-fast"))
    assert out is not None
    assert out.model == "pro", "relaxed acquire should fall back to any eligible key"
