from __future__ import annotations

from pathlib import Path

import pytest

from sonya.config import AppConfig, load_config


def test_config_loads_from_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SONYA_SUBSTRATE_PATH", str(tmp_path / "substrate.db"))
    monkeypatch.setenv("SONYA_HEALTH_PATH", str(tmp_path / "health.json"))
    monkeypatch.setenv("SONYA_LOG_LEVEL", "DEBUG")

    cfg = load_config()

    assert cfg.substrate_path == tmp_path / "substrate.db"
    assert cfg.health_path == tmp_path / "health.json"
    assert cfg.log_level == "DEBUG"


def test_config_uses_defaults_when_env_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    for var in ("SONYA_SUBSTRATE_PATH", "SONYA_HEALTH_PATH", "SONYA_LOG_LEVEL"):
        monkeypatch.delenv(var, raising=False)

    cfg = load_config()

    assert cfg.substrate_path.name == "sonya_substrate.db"
    assert cfg.health_path.name == "health.json"
    assert cfg.log_level == "INFO"


def test_config_paths_are_path_objects(tmp_path: Path) -> None:
    cfg = AppConfig(
        substrate_path=tmp_path / "x.db",
        health_path=tmp_path / "h.json",
        log_level="INFO",
    )
    assert isinstance(cfg.substrate_path, Path)
    assert isinstance(cfg.health_path, Path)
