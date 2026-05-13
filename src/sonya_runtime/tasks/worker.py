from __future__ import annotations

import argparse
import socket
import time
from pathlib import Path

from sonya_runtime.storage.paths import RuntimePaths
from sonya_runtime.tasks.executor import ALLOWED_TASK_KINDS, TaskExecutor
from sonya_runtime.tasks.sqlite_store import SQLiteTaskStore


def run_worker(openclaw_root: Path, *, once: bool = False, poll_interval: float = 5.0) -> int:
    runtime_paths = RuntimePaths(openclaw_root)
    store = SQLiteTaskStore(runtime_paths.tasks_db_path)
    executor = TaskExecutor(repo_root=Path(__file__).resolve().parents[3], openclaw_root=openclaw_root)
    worker_id = f"{socket.gethostname()}-{int(time.time())}"
    try:
        while True:
            task = store.claim_next_task(worker_id, allowed_kinds=set(ALLOWED_TASK_KINDS))
            if task is None:
                if once:
                    return 0
                time.sleep(poll_interval)
                continue
            try:
                result = executor.execute(task)
                store.mark_done(task.task_id, result.summary, result.payload)
            except Exception as err:
                store.mark_failed(task.task_id, str(err))
            if once:
                return 0
    finally:
        store.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--openclaw-root", default=r"C:\Users\Jester\.openclaw")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-interval", type=float, default=5.0)
    args = parser.parse_args(argv)
    return run_worker(Path(args.openclaw_root), once=args.once, poll_interval=args.poll_interval)


if __name__ == "__main__":
    raise SystemExit(main())
