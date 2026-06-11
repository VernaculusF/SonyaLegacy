"""Credentials must not enter Sonya's current situation model."""
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

def test_normal_env_set_works(env: EnvTool) -> None:
    out = env.set("ivan_status работает")
    assert "[OK]" in out


def test_env_set_short_keys(env: EnvTool) -> None:
    """Plain observations like mood, weather etc. don't trigger hint."""
    for key in ("mood", "weather", "current_focus", "ivan_status"):
        out = env.set(f"{key} something")
        assert "[OK]" in out


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
def test_credential_keys_are_rejected(env: EnvTool, key: str) -> None:
    out = env.set(f"{key} HudwffKMkZtBgHObPG9bKkxdyEUPkL2Q")
    assert "[ERROR]" in out
    assert "protected secret storage" in out
    assert "Hudwff" not in env.list_all()


def test_normal_value_can_be_superseded(env: EnvTool) -> None:
    env.set("ivan_status спит")
    env.set("ivan_status работает")
    assert "работает" in env.get("ivan_status")
    assert "спит" not in env.get("ivan_status")
