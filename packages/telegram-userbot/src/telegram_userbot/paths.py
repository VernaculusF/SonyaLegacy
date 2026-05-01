from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class OpenClawPaths:
    root: Path

    @property
    def workspace_root(self) -> Path:
        return self.root / "workspace"

    @property
    def config_path(self) -> Path:
        return self.root / "openclaw.json"

    @property
    def state_path(self) -> Path:
        return self.root / "telegram-bridge-state.json"

    @property
    def bridge_log_path(self) -> Path:
        return self.root / "telegram-bridge.log"

    @property
    def session_dir(self) -> Path:
        return self.root / "telegram-bridge-sessions"

    @property
    def raw_updates_path(self) -> Path:
        return self.root / "telegram" / "raw-updates.jsonl"

    @property
    def inbound_media_dir(self) -> Path:
        return self.root / "media" / "inbound"

    @property
    def generated_media_dir(self) -> Path:
        return self.root / "media" / "generated"

    @property
    def agents_path(self) -> Path:
        return self.workspace_root / "AGENTS.md"

    @property
    def soul_path(self) -> Path:
        return self.workspace_root / "SOUL.md"

    @property
    def heartbeat_path(self) -> Path:
        return self.workspace_root / "HEARTBEAT.md"

    @property
    def identity_path(self) -> Path:
        return self.workspace_root / "IDENTITY.md"

    @property
    def memory_system_root(self) -> Path:
        return self.workspace_root / "memory_system"

    @property
    def context_loader_path(self) -> Path:
        return self.memory_system_root / "context_loader.py"

    @property
    def post_response_hook_path(self) -> Path:
        return self.memory_system_root / "post_response_hook.py"
