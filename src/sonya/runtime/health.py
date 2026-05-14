from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from sonya import __version__


@dataclass(slots=True)
class Health:
    """File-based health ping. Updates `path` at `interval_seconds` cadence."""

    path: Path
    interval_seconds: float = 10.0
    _task: asyncio.Task | None = None
    _running: bool = False
    _started_at: str = ""
    _schema_version: int = 0
    _status: str = "starting"
    _last_ping_at: str = ""
    _stop_event: asyncio.Event = field(default_factory=asyncio.Event)

    async def start(self, *, schema_version: int) -> None:
        if self._running:
            return
        self._schema_version = schema_version
        self._started_at = _utc_now_iso()
        self._status = "running"
        self._stop_event = asyncio.Event()
        self._running = True
        await self._write_once()
        self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if not self._running:
            return
        self._status = "stopped"
        self._running = False
        self._stop_event.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=self.interval_seconds + 1)
            except asyncio.TimeoutError:
                self._task.cancel()
            self._task = None
        await self._write_once()

    async def _run(self) -> None:
        try:
            while self._running:
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=self.interval_seconds,
                    )
                except asyncio.TimeoutError:
                    await self._write_once()
                else:
                    return
        except asyncio.CancelledError:
            return

    async def _write_once(self) -> None:
        self._last_ping_at = _utc_now_iso()
        payload = {
            "pid": os.getpid(),
            "version": __version__,
            "schema_version": self._schema_version,
            "status": self._status,
            "started_at": self._started_at,
            "last_ping_at": self._last_ping_at,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(payload, ensure_ascii=False), encoding="utf-8"
        )

    @property
    def last_ping_at(self) -> str:
        return self._last_ping_at


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
