from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from sonya.config import AppConfig
from sonya.main import _run
from sonya.state import (
    ContinuityStream,
    IdentityWriter,
    Substrate,
)
from sonya.state.seed import THINGS_NOT_TO_BETRAY_SEED


def _drive_short_run(config: AppConfig) -> int:
    async def driver() -> int:
        run_task = asyncio.create_task(_run(config))
        await asyncio.sleep(0.3)
        run_task.cancel()
        try:
            await run_task
        except asyncio.CancelledError:
            return 0
        return 0

    return asyncio.run(driver())


def test_first_run_seeds_things_not_to_betray(tmp_path: Path) -> None:
    cfg = AppConfig(
        substrate_path=tmp_path / "s.db",
        health_path=tmp_path / "h.json",
        log_level="WARNING",
    )

    _drive_short_run(cfg)

    sub = Substrate.open(cfg.substrate_path)
    try:
        record = IdentityWriter(sub).load()
        assert set(record.things_not_to_betray) == set(THINGS_NOT_TO_BETRAY_SEED)
    finally:
        sub.close()


def test_first_run_records_governed_change_event(tmp_path: Path) -> None:
    cfg = AppConfig(
        substrate_path=tmp_path / "s.db",
        health_path=tmp_path / "h.json",
        log_level="WARNING",
    )

    _drive_short_run(cfg)

    sub = Substrate.open(cfg.substrate_path)
    try:
        events = list(ContinuityStream(sub).read_since(0))
        seed_events = [
            e
            for e in events
            if e.kind == "governed_identity_change"
            and e.payload.get("change_id") == "identity-seed"
        ]
        assert len(seed_events) == 1
    finally:
        sub.close()


def test_substrate_is_at_v2(tmp_path: Path) -> None:
    cfg = AppConfig(
        substrate_path=tmp_path / "s.db",
        health_path=tmp_path / "h.json",
        log_level="WARNING",
    )

    _drive_short_run(cfg)

    sub = Substrate.open(cfg.substrate_path)
    try:
        assert sub.schema_version >= 2
    finally:
        sub.close()


def test_second_run_does_not_re_seed(tmp_path: Path) -> None:
    cfg = AppConfig(
        substrate_path=tmp_path / "s.db",
        health_path=tmp_path / "h.json",
        log_level="WARNING",
    )

    _drive_short_run(cfg)
    _drive_short_run(cfg)

    sub = Substrate.open(cfg.substrate_path)
    try:
        events = list(ContinuityStream(sub).read_since(0))
        seed_events = [
            e
            for e in events
            if e.kind == "governed_identity_change"
            and e.payload.get("change_id") == "identity-seed"
        ]
        assert len(seed_events) == 1
    finally:
        sub.close()
