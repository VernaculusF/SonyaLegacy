from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class RuntimePaths:
    openclaw_root: Path

    @property
    def runtime_root(self) -> Path:
        return self.openclaw_root / "sonya_runtime"

    @property
    def tasks_db_path(self) -> Path:
        return self.runtime_root / "tasks.db"
