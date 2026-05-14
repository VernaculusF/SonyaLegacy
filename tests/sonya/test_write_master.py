from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from sonya.runtime.write_master import WriteMaster, WriteMasterContention


def test_acquire_creates_lock_file(tmp_path: Path) -> None:
    wm = WriteMaster.for_substrate(tmp_path / "s.db")
    wm.acquire()
    try:
        assert wm.lock_path.exists()
        data = json.loads(wm.lock_path.read_text(encoding="utf-8"))
        assert data["pid"] == os.getpid()
    finally:
        wm.release()


def test_release_removes_lock_file(tmp_path: Path) -> None:
    wm = WriteMaster.for_substrate(tmp_path / "s.db")
    wm.acquire()
    wm.release()
    assert not wm.lock_path.exists()


def test_second_acquire_with_live_pid_blocks(tmp_path: Path) -> None:
    wm1 = WriteMaster.for_substrate(tmp_path / "s.db")
    wm1.acquire()
    try:
        wm2 = WriteMaster.for_substrate(tmp_path / "s.db")
        with pytest.raises(WriteMasterContention):
            wm2.acquire()
    finally:
        wm1.release()


def test_stale_lock_with_dead_pid_is_taken(tmp_path: Path) -> None:
    lock_path = (tmp_path / "s.db.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    # PID that almost certainly doesn't exist (4-byte max)
    lock_path.write_text(json.dumps({"pid": 999_999_999, "acquired_at": "x"}), encoding="utf-8")
    wm = WriteMaster.for_substrate(tmp_path / "s.db")
    wm.acquire()
    try:
        data = json.loads(wm.lock_path.read_text(encoding="utf-8"))
        assert data["pid"] == os.getpid()
    finally:
        wm.release()


def test_context_manager_releases(tmp_path: Path) -> None:
    wm = WriteMaster.for_substrate(tmp_path / "s.db")
    with wm:
        assert wm.is_acquired
    assert not wm.is_acquired
    assert not wm.lock_path.exists()


def test_release_without_acquire_is_safe(tmp_path: Path) -> None:
    wm = WriteMaster.for_substrate(tmp_path / "s.db")
    wm.release()  # must not raise
