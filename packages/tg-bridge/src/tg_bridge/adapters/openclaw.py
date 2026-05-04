from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tg_bridge.config import read_json
from tg_bridge.paths import OpenClawPaths


@dataclass(frozen=True, slots=True)
class OpenClawHost:
    root: Path
    _paths: OpenClawPaths = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "root", Path(self.root))
        object.__setattr__(self, "_paths", OpenClawPaths(Path(self.root)))

    @property
    def paths(self) -> OpenClawPaths:
        return getattr(self, "_paths")

    @property
    def config_path(self) -> Path:
        return self.paths.config_path

    @property
    def workspace_root(self) -> Path:
        return self.paths.workspace_root

    @property
    def bridge_log_path(self) -> Path:
        return self.paths.bridge_log_path

    @property
    def state_path(self) -> Path:
        return self.paths.state_path

    @property
    def session_dir(self) -> Path:
        return self.paths.session_dir

    @property
    def raw_updates_path(self) -> Path:
        return self.paths.raw_updates_path

    @property
    def inbound_media_dir(self) -> Path:
        return self.paths.inbound_media_dir

    @property
    def generated_media_dir(self) -> Path:
        return self.paths.generated_media_dir

    @property
    def agents_path(self) -> Path:
        return self.paths.agents_path

    @property
    def soul_path(self) -> Path:
        return self.paths.soul_path

    @property
    def heartbeat_path(self) -> Path:
        return self.paths.heartbeat_path

    @property
    def identity_path(self) -> Path:
        return self.paths.identity_path

    @property
    def context_loader_path(self) -> Path:
        return self.paths.context_loader_path

    @property
    def post_response_hook_path(self) -> Path:
        return self.paths.post_response_hook_path

    def load_config(self) -> dict[str, Any]:
        return read_json(self.config_path)

