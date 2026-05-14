from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from sonya.runtime import Health


@pytest.mark.asyncio
async def test_health_writes_initial_ping_on_start(tmp_path: Path) -> None:
    health = Health(path=tmp_path / "health.json", interval_seconds=10.0)
    try:
        await health.start(schema_version=1)
        assert (tmp_path / "health.json").exists()
        payload = json.loads((tmp_path / "health.json").read_text(encoding="utf-8"))
        assert payload["status"] == "running"
        assert payload["schema_version"] == 1
        assert payload["pid"] > 0
        assert payload["last_ping_at"]
    finally:
        await health.stop()


@pytest.mark.asyncio
async def test_health_updates_ping_on_interval(tmp_path: Path) -> None:
    health = Health(path=tmp_path / "health.json", interval_seconds=0.05)
    try:
        await health.start(schema_version=1)
        first = json.loads((tmp_path / "health.json").read_text(encoding="utf-8"))[
            "last_ping_at"
        ]
        await asyncio.sleep(0.15)
        second = json.loads((tmp_path / "health.json").read_text(encoding="utf-8"))[
            "last_ping_at"
        ]
        assert first != second
    finally:
        await health.stop()


@pytest.mark.asyncio
async def test_health_status_reflects_stop(tmp_path: Path) -> None:
    health = Health(path=tmp_path / "health.json", interval_seconds=10.0)
    await health.start(schema_version=1)
    await health.stop()
    payload = json.loads((tmp_path / "health.json").read_text(encoding="utf-8"))
    assert payload["status"] == "stopped"


@pytest.mark.asyncio
async def test_health_includes_version_field(tmp_path: Path) -> None:
    health = Health(path=tmp_path / "health.json", interval_seconds=10.0)
    try:
        await health.start(schema_version=1)
        payload = json.loads((tmp_path / "health.json").read_text(encoding="utf-8"))
        assert payload["version"]
    finally:
        await health.stop()
