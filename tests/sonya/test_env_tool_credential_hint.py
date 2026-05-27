"""Tests for the credential-shape hint in env.set.

Symptom from 27.05.20:31 mpbacademy session: Ivan gave Sonya a Shodan
API key and asked her to store it. She wrote `env.set apikey_openrouter
HudwffK...` (wrong label — she had verified it as Shodan that morning),
then later tried to use it as OpenRouter, got 401, told Ivan the key
was invalid, then apologised when Ivan corrected her.

Fix isn't a hard gate (we don't want RLHF-style refusal layers). It's
a soft hint appended to the [OK] result: "this is credential-shaped,
verify label via memory.recall before using". The model can ignore it
but it's there as a reminder.

Also detects label-drift overwrites (existing value differs from the
new one) — separate hint about overwriting a credential.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from sonya.state.substrate import Substrate
from sonya.state import seed_identity_if_empty
from sonya.tools.env_tool import EnvTool


@pytest.fixture
def env(tmp_path: Path):
    sub = Substrate.open(tmp_path / "test.db")
    seed_identity_if_empty(sub)
    yield EnvTool(sub)
    sub.close()


# --- normal env.set still works ---

def test_normal_env_set_no_hint(env: EnvTool) -> None:
    """Non-credential keys get the plain [OK] reply, no hint suffix."""
    out = env.set("ivan_status работает")
    assert "[OK]" in out
    assert "[hint]" not in out


def test_env_set_short_keys(env: EnvTool) -> None:
    """Plain observations like mood, weather etc. don't trigger hint."""
    for key in ("mood", "weather", "current_focus", "ivan_status"):
        out = env.set(f"{key} something")
        assert "[hint]" not in out, f"unexpected hint on {key}"


# --- credential-shape detection ---

@pytest.mark.parametrize("key", [
    "apikey_shodan",
    "apikey_openrouter",
    "api_key_fireworks",
    "shodan_apikey",
    "github_token",
    "auth_token",
    "secret_key",
    "client_secret",
    "credential_main",
])
def test_credential_keys_get_hint(env: EnvTool, key: str) -> None:
    out = env.set(f"{key} HudwffKMkZtBgHObPG9bKkxdyEUPkL2Q")
    assert "[OK]" in out
    assert "[hint]" in out
    assert "memory.recall" in out
    assert "credential-shaped" in out


# --- overwrite detection ---

def test_overwrite_credential_adds_overwrite_note(env: EnvTool) -> None:
    """If we set apikey_x to value A, then to value B, the second call's
    hint should mention 'overwriting'."""
    env.set("apikey_test value-aaaaaaaaa")
    out2 = env.set("apikey_test value-bbbbbbbbb")
    assert "[hint]" in out2
    assert "overwriting" in out2.lower()


def test_setting_same_value_no_overwrite_note(env: EnvTool) -> None:
    """Same value twice — no overwrite note (it's idempotent)."""
    env.set("apikey_test same-value-xx")
    out2 = env.set("apikey_test same-value-xx")
    assert "[hint]" in out2  # still credential-shape hint
    assert "overwriting" not in out2.lower()


def test_first_set_no_overwrite_note(env: EnvTool) -> None:
    """First-time set never has overwrite note."""
    out = env.set("apikey_brandnew somevalue")
    assert "[hint]" in out
    assert "overwriting" not in out.lower()


# --- hint is informational, not blocking ---

def test_value_actually_persisted_with_hint(env: EnvTool) -> None:
    """The hint doesn't prevent the value from being stored. Sonya can
    still proceed; the hint is just a reminder she might verify the label."""
    env.set("apikey_thing HudwffKMkZtBgHObPG9bKkxdyEUPkL2Q")
    fetched = env.get("apikey_thing")
    assert "HudwffKMkZtBgHObPG9bKkxdyEUPkL2Q" in fetched


def test_hint_does_not_truncate_ok_message(env: EnvTool) -> None:
    """The [OK] line and the [hint] line should both be present, with the
    [OK] line still readable as the leading status."""
    out = env.set("apikey_x test-value")
    first_line = out.split("\n")[0]
    assert first_line.startswith("[OK]")
