from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# Load .env file if exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed, rely on actual env vars


_DEFAULT_DATA_ROOT = Path.home() / ".sonya"


@dataclass(frozen=True, slots=True)
class AppConfig:
    """Runtime configuration. No secrets stored here; secrets stay in env."""

    substrate_path: Path
    health_path: Path
    log_level: str = "INFO"
    tg_api_id: int = 0
    tg_api_hash: str = ""
    tg_session_path: str = ""
    primary_user_tg_id: str = ""
    tg_allowed_extra_senders: str = ""  # comma-separated tg sender_ids beyond primary
    enable_telegram: bool = True
    enable_thinking: bool = True
    initiative_max_per_day: int = 5
    initiative_min_quiet_minutes: int = 90  # how long since last contact before initiative is allowed
    progress_updates_max_per_day: int = 50  # streaming chat.tell_ivan inside agent sessions
    yolo_mode: bool = True  # default: shell.run / pip.install execute without approval. Personal env, not a hosted product.
    media_dir: Path = _DEFAULT_DATA_ROOT / "media"  # where incoming media is downloaded
    # Atrium Этап 1.5 — TG becomes emergency-only once Atrium is the primary
    # dialog surface. When True, `chat.dialog` is suppressed from TG as long as
    # Atrium was seen within `tg_emergency_threshold_hours`. Real emergencies
    # (Atrium offline past threshold, or explicit emergency_override) still go.
    tg_emergency_mode: bool = False
    tg_emergency_threshold_hours: float = 24.0


def _env_path(name: str, default: Path) -> Path:
    raw = os.environ.get(name)
    return Path(raw) if raw else default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.lower() in ("1", "true", "yes", "on")


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
    tg_api_id = int(os.environ.get("SONYA_TG_API_ID", "0"))
    tg_api_hash = os.environ.get("SONYA_TG_API_HASH", "")
    tg_session_path = os.environ.get("SONYA_TG_SESSION_PATH", "")
    primary_user_tg_id = os.environ.get("SONYA_PRIMARY_USER_TG_ID", "")
    tg_allowed_extra_senders = os.environ.get("SONYA_TG_ALLOWED_EXTRA_SENDERS", "")
    enable_telegram = _env_bool("SONYA_ENABLE_TELEGRAM", True)
    enable_thinking = _env_bool("SONYA_ENABLE_THINKING", True)
    initiative_max_per_day = int(os.environ.get("SONYA_INITIATIVE_MAX_PER_DAY", "5"))
    initiative_min_quiet_minutes = int(os.environ.get("SONYA_INITIATIVE_MIN_QUIET_MINUTES", "90"))
    progress_updates_max_per_day = int(os.environ.get("SONYA_PROGRESS_UPDATES_MAX_PER_DAY", "50"))
    yolo_mode = _env_bool("SONYA_YOLO_MODE", True)
    media_dir = _env_path("SONYA_MEDIA_DIR", _DEFAULT_DATA_ROOT / "media")
    tg_emergency_mode = _env_bool("SONYA_TG_EMERGENCY_MODE", False)
    try:
        tg_emergency_threshold_hours = float(
            os.environ.get("SONYA_TG_EMERGENCY_THRESHOLD_HOURS", "24")
        )
    except ValueError:
        tg_emergency_threshold_hours = 24.0
    return AppConfig(
        substrate_path=substrate_path,
        health_path=health_path,
        log_level=log_level,
        tg_api_id=tg_api_id,
        tg_api_hash=tg_api_hash,
        tg_session_path=tg_session_path,
        primary_user_tg_id=primary_user_tg_id,
        tg_allowed_extra_senders=tg_allowed_extra_senders,
        enable_telegram=enable_telegram,
        enable_thinking=enable_thinking,
        initiative_max_per_day=initiative_max_per_day,
        initiative_min_quiet_minutes=initiative_min_quiet_minutes,
        progress_updates_max_per_day=progress_updates_max_per_day,
        yolo_mode=yolo_mode,
        media_dir=media_dir,
        tg_emergency_mode=tg_emergency_mode,
        tg_emergency_threshold_hours=tg_emergency_threshold_hours,
    )
