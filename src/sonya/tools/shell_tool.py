"""Shell tool: gated through ApprovalManager.

Workflow:
  1. Sonya calls shell.run "apt list --installed | grep python"
     → If no approval exists for this exact command, returns
       "[PENDING_APPROVAL: req_id]" and creates an ApprovalRequest.
  2. Ivan approves via admin panel.
  3. Sonya calls shell.run again with the same command.
     → ApprovalManager finds the approved request, marks it consumed,
       runs the command.

Same flow for `pip.install <package>`. Both record the resolved exit code,
stdout/stderr in continuity stream so approval audit trail is complete.

Sonya should pair this with `tasks.block` so she can pause work and
pick up after Ivan approves: `tasks.block <id> | waiting on shell approval req-xxx`.
"""
from __future__ import annotations

import hashlib
import os
import subprocess
from typing import Iterable

from sonya.harness.approval import (
    ApprovalAlreadyDecidedError,
    ApprovalManager,
    ApprovalNotFoundError,
    ApprovalStatus,
)
from sonya.state.continuity_stream import ContinuityEvent, ContinuityStream
from sonya.state.substrate import Substrate


_DEFAULT_TIMEOUT = 60  # seconds
_MAX_OUTPUT_BYTES = 200_000

_SHELL_ACTION_PREFIX = "shell.run:"
_PIP_ACTION_PREFIX = "pip.install:"


def _hash_command(cmd: str) -> str:
    return hashlib.sha256(cmd.encode("utf-8")).hexdigest()[:16]


class ShellTool:
    """Gated shell + pip. Requires Ivan approval per unique command."""

    def __init__(
        self,
        substrate: Substrate,
        *,
        principal_id: str,
        stream: ContinuityStream | None = None,
        timeout_seconds: int = _DEFAULT_TIMEOUT,
        pip_executable: Iterable[str] = ("pip",),
    ) -> None:
        self._sub = substrate
        self._approval = ApprovalManager(substrate)
        self._principal_id = principal_id
        self._stream = stream
        self._timeout = timeout_seconds
        self._pip = list(pip_executable)

    # ---------- public ----------

    def run_shell(self, cmd: str) -> str:
        cmd = cmd.strip()
        if not cmd:
            return "[ERROR] shell.run needs a command"
        return self._gated_run(
            action=f"{_SHELL_ACTION_PREFIX}{_hash_command(cmd)}",
            scope=cmd,
            argv=["/bin/sh", "-c", cmd],
            kind="shell.executed",
        )

    def install_pip(self, package: str) -> str:
        package = package.strip()
        if not package:
            return "[ERROR] pip.install needs a package name"
        # Reject obvious shell-injection garbage; pip can take VCS URLs but
        # for now we keep it simple — names + versions only.
        if any(c in package for c in (";", "&", "|", "`", "$", "\n")):
            return "[ERROR] pip.install: invalid characters in package name"
        return self._gated_run(
            action=f"{_PIP_ACTION_PREFIX}{_hash_command(package)}",
            scope=f"pip install {package}",
            argv=[*self._pip, "install", "--no-input", package],
            kind="pip.installed",
        )

    # ---------- gating ----------

    def _gated_run(
        self,
        *,
        action: str,
        scope: str,
        argv: list[str],
        kind: str,
    ) -> str:
        # Look for existing approval for this exact action.
        existing = self._approval.find_by_action_pattern(action)
        approved = next((r for r in existing if r.status is ApprovalStatus.APPROVED), None)
        denied = next((r for r in existing if r.status is ApprovalStatus.DENIED), None)
        pending = next((r for r in existing if r.status is ApprovalStatus.PENDING), None)

        if denied is not None:
            return f"[DENIED] {scope}\n  request {denied.request_id} was denied at {denied.decided_at}"

        if approved is None:
            if pending is not None:
                return (
                    f"[PENDING_APPROVAL: {pending.request_id}] {scope}\n"
                    f"Ivan needs to approve this in admin panel.\n"
                    f"Use tasks.block to pause and continue after approval."
                )
            new_req = self._approval.create(
                principal_id=self._principal_id,
                action=action,
                scope=scope,
            )
            self._emit("approval.requested", {
                "request_id": new_req.request_id,
                "action": action,
                "scope": scope[:300],
            })
            return (
                f"[PENDING_APPROVAL: {new_req.request_id}] {scope}\n"
                f"Created approval request. Ivan needs to approve in admin panel.\n"
                f"Use tasks.block to pause and continue after approval."
            )

        # Approved — execute.
        result = self._execute(argv)
        self._emit(kind, {
            "request_id": approved.request_id,
            "scope": scope[:300],
            "exit_code": result.get("exit", -1),
            "stdout_bytes": len(result.get("stdout", "")),
            "stderr_bytes": len(result.get("stderr", "")),
        })
        return self._format_result(scope, approved.request_id, result)

    # ---------- subprocess ----------

    def _execute(self, argv: list[str]) -> dict:
        env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": os.environ.get("HOME", "/tmp"),
            "PYTHONIOENCODING": "utf-8",
        }
        try:
            proc = subprocess.run(
                argv,
                env=env,
                capture_output=True,
                timeout=self._timeout,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {"exit": -1, "stdout": "", "stderr": f"[TIMEOUT after {self._timeout}s]"}
        except Exception as err:
            return {"exit": -1, "stdout": "", "stderr": f"[SPAWN FAIL] {type(err).__name__}: {err}"}
        return {
            "exit": proc.returncode,
            "stdout": proc.stdout.decode("utf-8", errors="replace")[:_MAX_OUTPUT_BYTES],
            "stderr": proc.stderr.decode("utf-8", errors="replace")[:_MAX_OUTPUT_BYTES],
        }

    def _format_result(self, scope: str, req_id: str, result: dict) -> str:
        parts = [
            f"[OK approved={req_id}] {scope}",
            f"exit: {result.get('exit', -1)}",
        ]
        stdout = result.get("stdout", "")
        stderr = result.get("stderr", "")
        if stdout:
            parts.append(f"--- stdout ---\n{stdout}")
        if stderr:
            parts.append(f"--- stderr ---\n{stderr}")
        if not stdout and not stderr:
            parts.append("(no output)")
        return "\n".join(parts)

    def _emit(self, kind: str, payload: dict) -> None:
        if self._stream is None:
            return
        try:
            self._stream.append(ContinuityEvent(
                kind=kind,
                principal_id=self._principal_id,
                payload=payload,
            ))
        except Exception:
            pass
