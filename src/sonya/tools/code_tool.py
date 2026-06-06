"""Code execution tool: sandboxed Python via subprocess.

Each call spawns a fresh Python process with a temp dir as cwd, no env
inheritance beyond PATH/HOME, and a hard wall-clock timeout. Stdout/stderr
captured. No persistence between calls (fresh interpreter each time).

This is NOT a strong sandbox. Code can:
- read/write under the temp dir
- access files the user can access
- make network calls (we don't bind-mount /etc/resolv.conf so outbound DNS works)

It is meant for "I want to compute something / try out a snippet". For
anything that needs to *change* Sonya's environment, use selfmod or
shell.run (which is approval-gated).
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path


_DEFAULT_TIMEOUT = 30  # seconds
_MAX_OUTPUT_BYTES = 200_000


class CodeTool:
    def __init__(self, *, python_executable: str | None = None, timeout_seconds: int = _DEFAULT_TIMEOUT, sandbox_dir: str | None = None) -> None:
        self._python = python_executable or sys.executable
        self._timeout = timeout_seconds
        self._sandbox_dir = sandbox_dir

    def exec_python(self, code: str) -> str:
        if not code.strip():
            return "[ERROR] code.exec needs python code"

        # Strip optional ```python ... ``` fence the model may emit defensively.
        code = code.strip()
        if code.startswith("```"):
            # Remove first fence line
            first_nl = code.find("\n")
            if first_nl != -1:
                code = code[first_nl + 1:]
            # Remove trailing fence
            if code.rstrip().endswith("```"):
                code = code.rstrip()[:-3]
        code = textwrap.dedent(code).strip()
        try:
            compile(code, "<code.exec>", "exec")
        except SyntaxError as err:
            return f"[ERROR] SyntaxError: {err.msg} (line {err.lineno})"

        with tempfile.TemporaryDirectory(prefix="sonya-code-") as tmp:
            script_path = Path(tmp) / "script.py"
            script_path.write_text(code, encoding="utf-8")
            
            run_cwd = tmp
            if self._sandbox_dir:
                run_cwd = self._sandbox_dir

            # Use the real user HOME so `~` resolves correctly.
            # Sonya needs to reach her runtime data (~/.sonya/sonya_substrate.db)
            # and her own source code (~/Sonya/src/...). The temp dir is
            # communicated via TMPDIR; python's tempfile.gettempdir() honours it.
            # Other env vars are deliberately stripped to prevent key leakage.
            real_home = os.environ.get("HOME") or os.path.expanduser("~")
            env = {
                "PATH": os.environ.get("PATH", ""),
                "HOME": real_home,
                "TMPDIR": tmp,
                "PYTHONIOENCODING": "utf-8",
                "PYTHONDONTWRITEBYTECODE": "1",
            }
            try:
                proc = subprocess.run(
                    [self._python, str(script_path)],
                    cwd=run_cwd,
                    env=env,
                    capture_output=True,
                    timeout=self._timeout,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                return f"[TIMEOUT] code.exec exceeded {self._timeout}s wall clock"
            except Exception as err:
                return f"[ERROR] code.exec failed to spawn: {type(err).__name__}: {err}"

        stdout = proc.stdout.decode("utf-8", errors="replace")[:_MAX_OUTPUT_BYTES]
        stderr = proc.stderr.decode("utf-8", errors="replace")[:_MAX_OUTPUT_BYTES]

        parts: list[str] = [f"[exit {proc.returncode}]"]
        if stdout:
            parts.append(f"--- stdout ---\n{stdout}")
        if stderr:
            parts.append(f"--- stderr ---\n{stderr}")
        if not stdout and not stderr:
            parts.append("(no output)")
        return "\n".join(parts)
