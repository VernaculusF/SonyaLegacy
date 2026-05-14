from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


_DEFAULT_DATA_ROOT = Path.home() / ".sonya"


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Runtime configuration. No secrets stored here; secrets stay in env."""

    substrate_path: Path
    health_path: Path
    log_level: str = "INFO"


def _env_path(name: str, default: Path) -> Path:
    raw = os.environ.get(name)
    return Path(raw) if raw else default


def load_config() -> AppConfig:
    """Load AppConfig from environment variables with sensible defaults."""
    substrate_path = _env_path(
        "SONYA_SUBSTRATE_PATH",
        _DEFAULT_DATA_ROOT / "sonya_substrate.db",
    )
    health_path = _env_path(
        "SONYA_HEALTH_PATH",
        _DEFAULT_DATA_ROOT / "health.json",
    )
    log_level = os.environ.get("SONYA_LOG_LEVEL", "INFO").upper()
    return AppConfig(
        substrate_path=substrate_path,
        health_path=health_path,
        log_level=log_level,
    )
