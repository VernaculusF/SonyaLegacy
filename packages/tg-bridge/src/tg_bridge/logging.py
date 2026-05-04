from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


def format_error(err) -> str:
    if not err:
        return "unknown error"
    parts: list[str] = []
    parts.append(type(err).__name__)
    if getattr(err, "message", None):
        parts.append(str(err.message))
    elif str(err):
        parts.append(str(err))
    cause = getattr(err, "__cause__", None)
    if cause and str(cause):
        parts.append(f"cause={cause}")
    code = getattr(err, "code", None)
    if code:
        parts.append(f"code={code}")
    return " | ".join(parts) if parts else str(err)


def append_log_line(log_path: Path, message: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    with log_path.open("a", encoding="utf-8") as handle:
        handle.write(f"{timestamp} {message}\n")

