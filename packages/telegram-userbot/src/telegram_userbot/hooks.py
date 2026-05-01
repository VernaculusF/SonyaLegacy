from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any


def build_hook_env(
    workspace_root: Path,
    session_id: str,
    user_text: str,
    assistant_text: str,
    base_env: dict[str, str] | None = None,
) -> dict[str, str]:
    env = dict(base_env or os.environ)
    env.update(
        {
            "OPENCLAW_WORKSPACE": str(workspace_root),
            "OPENCLAW_SESSION_ID": session_id,
            "OPENCLAW_LAST_USER_MSG": user_text,
            "OPENCLAW_LAST_ASSISTANT_MSG": assistant_text,
        }
    )
    return env


def run_python_hook(
    python_executable: Path,
    hook_path: Path,
    workspace_root: Path,
    session_id: str,
    user_text: str,
    assistant_text: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(python_executable), str(hook_path)],
        cwd=str(workspace_root),
        env=build_hook_env(workspace_root, session_id, user_text, assistant_text),
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )


def run_post_response_hook(
    session_id: str,
    user_text: str,
    assistant_text: str,
    runner: Callable[[str, str, str], Any],
) -> Any:
    return runner(session_id, user_text, assistant_text)
