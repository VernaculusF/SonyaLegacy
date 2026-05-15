from __future__ import annotations

import pytest

from sonya.providers import ProviderSecret, load_provider_secret


def test_secret_repr_redacts_value() -> None:
    s = ProviderSecret("super-secret-key-abcdef")
    assert "super-secret" not in repr(s)
    assert "abcdef" not in repr(s)


def test_secret_get_returns_value() -> None:
    s = ProviderSecret("k1")
    assert s.get_secret_value() == "k1"


def test_secret_str_redacts_value() -> None:
    s = ProviderSecret("k1")
    assert "k1" not in str(s)


def test_load_provider_secret_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SONYA_OPENROUTER_API_KEY", "env-key")
    secret = load_provider_secret("openrouter")
    assert secret is not None
    assert secret.get_secret_value() == "env-key"


def test_load_provider_secret_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SONYA_OPENROUTER_API_KEY", raising=False)
    assert load_provider_secret("openrouter") is None
