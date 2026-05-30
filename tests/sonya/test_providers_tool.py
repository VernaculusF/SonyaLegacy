"""ProvidersTool — list/balance/health smoke tests + balance() bug regression.

Regression for 30.05 TypeError: `_fmt_key` did `f"balance=${k.balance:.2f}"`
treating `ProviderKey.balance` as a number, but it's a method returning a
dict. Calling providers.list_keys crashed any session.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from sonya.providers.keystore import KeyStore
from sonya.state.substrate import Substrate
from sonya.tools.providers_tool import (
    ProvidersTool,
    _fmt_key,
    _key_balance_amount,
)


@pytest.fixture
def substrate(tmp_path):
    sub = Substrate.open(tmp_path / "p.db")
    yield sub
    sub.close()


def _seed(store: KeyStore, *, name: str, balance: dict | None = None) -> None:
    key = store.add_key(
        provider="fireworks",
        name=name,
        api_key=f"fw_{name}",
        base_url="https://api.fireworks.ai/inference/v1",
        slot="text",
    )
    if balance is not None:
        store.update_balance(key.key_id, account_id="acc-" + name, balance=balance)


def test_fmt_key_no_balance_does_not_crash(substrate):
    store = KeyStore(substrate)
    _seed(store, name="fresh")  # no balance snapshot
    keys = store.list_keys()
    assert len(keys) == 1
    text = _fmt_key(keys[0])
    assert "fresh" in text
    assert "balance=" not in text  # silent when unknown


def test_fmt_key_with_known_balance_prints_amount(substrate):
    store = KeyStore(substrate)
    _seed(store, name="paid", balance={"balance": 12.34})
    keys = store.list_keys()
    assert "balance=$12.34" in _fmt_key(keys[0])


def test_fmt_key_with_alt_balance_keys(substrate):
    store = KeyStore(substrate)
    _seed(store, name="kr1", balance={"usd": 5.55})
    _seed(store, name="or1", balance={"remaining": 7.0})
    _seed(store, name="cr1", balance={"credits": 0.5})
    keys = {k.name: k for k in store.list_keys()}
    assert "balance=$5.55" in _fmt_key(keys["kr1"])
    assert "balance=$7.00" in _fmt_key(keys["or1"])
    assert "balance=$0.50" in _fmt_key(keys["cr1"])


def test_balance_amount_helper_handles_garbage(substrate):
    store = KeyStore(substrate)
    _seed(store, name="weird", balance={"balance": "not-a-number"})
    keys = store.list_keys()
    # Doesn't crash; returns None when value unparseable.
    assert _key_balance_amount(keys[0]) is None


def test_list_keys_runs_without_crash(substrate):
    """The original 30.05 bug — list_keys() crashed with TypeError on
    `f"balance=${k.balance:.2f}"` because k.balance is a method."""
    store = KeyStore(substrate)
    _seed(store, name="k1")
    _seed(store, name="k2", balance={"balance": 3.14})
    out = ProvidersTool(substrate).list_keys()
    assert "k1" in out
    assert "k2" in out
    assert "balance=$3.14" in out


def test_health_report_no_active_keys(substrate):
    out = ProvidersTool(substrate).health_report()
    assert "CRITICAL" in out and "0 активных" in out


def test_health_report_active_no_balance(substrate):
    store = KeyStore(substrate)
    _seed(store, name="active-no-bal")
    out = ProvidersTool(substrate).health_report()
    assert "UNKNOWN" in out


def test_health_report_warning_low_balance(substrate):
    store = KeyStore(substrate)
    _seed(store, name="low", balance={"balance": 2.0})
    out = ProvidersTool(substrate).health_report()
    assert "WARNING" in out
    assert "$2.00" in out


def test_health_report_ok(substrate):
    store = KeyStore(substrate)
    _seed(store, name="rich", balance={"balance": 50.0})
    out = ProvidersTool(substrate).health_report()
    assert out.startswith("[OK]")
