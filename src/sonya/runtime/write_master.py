from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


class WriteMasterContention(RuntimeError):
    """Another live process already holds the write-master lock."""


@dataclass(slots=True)
class WriteMaster:
    """File-based advisory lock with PID liveness check.

    Pure file lock — does not touch substrate's sqlite. Substrate write-side
    correctness is handled by SQLite itself; this lock just enforces that
    only one process at a time is allowed to be the master writer.
    """

    lock_path: Path
    _acquired: bool = False

    @classmethod
    def for_substrate(cls, substrate_path: Path | str) -> "WriteMaster":
        substrate_path = Path(substrate_path)
        return cls(lock_path=substrate_path.with_suffix(substrate_path.suffix + ".lock"))

    @classmethod
    def is_held(cls, substrate_path: Path | str) -> bool:
        """Check if substrate's write-master lock is held by a live process.

        Read-only check: does not modify the lock file. Useful for non-master
        processes (admin panel) to detect when core is running.
        """
        substrate_path = Path(substrate_path)
        lock_path = substrate_path.with_suffix(substrate_path.suffix + ".lock")
        try:
            data = json.loads(lock_path.read_text(encoding="utf-8"))
            pid = int(data.get("pid"))
        except (FileNotFoundError, json.JSONDecodeError, TypeError, ValueError):
            return False
        return _pid_alive(pid)

    def acquire(self) -> None:
        existing_pid = self._read_lock_pid()
        if existing_pid is not None and _pid_alive(existing_pid):
            raise WriteMasterContention(
                f"write-master already held by PID {existing_pid}"
            )
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "pid": os.getpid(),
            "acquired_at": datetime.now(timezone.utc).isoformat(),
        }
        self.lock_path.write_text(json.dumps(payload), encoding="utf-8")
        self._acquired = True

    def release(self) -> None:
        if not self._acquired:
            return
        try:
            self.lock_path.unlink()
        except FileNotFoundError:
            pass
        self._acquired = False

    def __enter__(self) -> "WriteMaster":
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()

    @property
    def is_acquired(self) -> bool:
        return self._acquired

    def _read_lock_pid(self) -> int | None:
        try:
            data = json.loads(self.lock_path.read_text(encoding="utf-8"))
            return int(data.get("pid"))
        except FileNotFoundError:
            return None
        except (json.JSONDecodeError, TypeError, ValueError):
            return None


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        return _pid_alive_windows(pid)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def _pid_alive_windows(pid: int) -> bool:
    import ctypes
    from ctypes import wintypes

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    STILL_ACTIVE = 259

    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return False
    try:
        exit_code = wintypes.DWORD()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return False
        return exit_code.value == STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)
