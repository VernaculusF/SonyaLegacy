"""Project workspace transports for local and SSH-connected systems."""
from __future__ import annotations

import base64
import json
import os
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

from sonya.tools.filesystem import FilesystemTool


_MAX_OUTPUT_BYTES = 200_000
_REMOTE_SCRIPT = r"""
import json, os, pathlib, subprocess, sys, tempfile
p=json.loads(__import__("base64").b64decode(sys.argv[1]).decode())
root=pathlib.Path(p["root"]).resolve()
target=(root / p.get("path", "")).resolve()
try: target.relative_to(root)
except ValueError: raise SystemExit("path outside workspace")
forbidden={".env",".env.local",".git","tg.session","tg.session-journal"}
if any(part in forbidden for part in target.parts): raise SystemExit("forbidden workspace path")
op=p["op"]
if op=="probe":
 print(json.dumps({"ok": root.is_dir()}))
elif op=="read":
 print(target.read_text(encoding="utf-8", errors="replace")[:10000])
elif op=="list":
 print("\n".join(("d " if x.is_dir() else "f ")+x.name for x in sorted(target.iterdir()) if x.name not in forbidden)[:20000])
elif op=="search":
 needle=p["needle"].lower(); out=[]
 for base, dirs, files in os.walk(root):
  dirs[:]=[d for d in dirs if d not in forbidden|{"node_modules","__pycache__"}]
  for name in files:
   if name in forbidden: continue
   path=pathlib.Path(base)/name
   try:
    for n,line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(),1):
     if needle in line.lower(): out.append(f"{path.relative_to(root)}:{n}: {line[:300]}")
     if len(out)>=100: break
   except Exception: pass
   if len(out)>=100: break
  if len(out)>=100: break
 print("\n".join(out))
elif op=="exec_python":
 with tempfile.NamedTemporaryFile("w", suffix=".py", encoding="utf-8", delete=False) as f:
  f.write(p["code"]); script=f.name
 try:
  r=subprocess.run([sys.executable, script], cwd=root, capture_output=True, timeout=p["timeout"], check=False)
  print(json.dumps({"exit":r.returncode,"stdout":r.stdout.decode("utf-8","replace"),"stderr":r.stderr.decode("utf-8","replace")}))
 finally: pathlib.Path(script).unlink(missing_ok=True)
"""
_REMOTE_SCRIPT_B64 = base64.b64encode(_REMOTE_SCRIPT.encode()).decode()


@dataclass(frozen=True, slots=True)
class SSHWorkspace:
    target: str
    root: str
    port: int | None = None


def parse_ssh_workspace(value: str) -> SSHWorkspace | None:
    if not value.startswith("ssh://"):
        return None
    parsed = urlsplit(value)
    if parsed.scheme != "ssh" or not parsed.hostname or not parsed.path.startswith("/"):
        raise ValueError("SSH workspace must be ssh://user@host[:port]/absolute/path")
    if parsed.password or parsed.query or parsed.fragment:
        raise ValueError("SSH workspace URI must not contain passwords, query, or fragment")
    user = parsed.username
    target = f"{user}@{parsed.hostname}" if user else parsed.hostname
    root = str(PurePosixPath(unquote(parsed.path)))
    return SSHWorkspace(target=target, root=root, port=parsed.port)


class SSHWorkspaceTool:
    def __init__(self, workspace: SSHWorkspace, *, timeout_seconds: int = 30) -> None:
        self._workspace = workspace
        self._timeout = timeout_seconds

    def probe(self) -> bool:
        result = self._invoke({"op": "probe", "root": self._workspace.root, "path": ""})
        try:
            return bool(json.loads(result).get("ok"))
        except Exception:
            return False

    def read_file(self, path: str) -> str:
        return self._safe_invoke("read", path=path)

    def list_dir(self, path: str = "") -> str:
        return self._safe_invoke("list", path=path)

    def search(self, query: str) -> str:
        query = (query or "").strip()
        if not query:
            return "[ERROR] filesystem.search needs a query"
        return self._safe_invoke("search", needle=query)

    def exec_python(self, code: str) -> str:
        if not (code or "").strip():
            return "[ERROR] code.exec needs python code"
        try:
            raw = self._invoke({
                "op": "exec_python",
                "root": self._workspace.root,
                "path": "",
                "code": code,
                "timeout": self._timeout,
            })
            result = json.loads(raw)
        except Exception as err:
            return f"[ERROR] remote code.exec failed: {type(err).__name__}: {err}"
        parts = [f"[exit {result.get('exit', -1)}]"]
        if result.get("stdout"):
            parts.append(f"--- stdout ---\n{str(result['stdout'])[:_MAX_OUTPUT_BYTES]}")
        if result.get("stderr"):
            parts.append(f"--- stderr ---\n{str(result['stderr'])[:_MAX_OUTPUT_BYTES]}")
        return "\n".join(parts)

    def _safe_invoke(self, op: str, **payload) -> str:
        try:
            return self._invoke({"op": op, "root": self._workspace.root, **payload})
        except Exception as err:
            return f"[ERROR] remote workspace {op} failed: {type(err).__name__}: {err}"

    def _invoke(self, payload: dict) -> str:
        encoded = base64.b64encode(json.dumps(payload).encode()).decode()
        command = (
            "python3 -c "
            + shlex.quote(f"import base64;exec(base64.b64decode('{_REMOTE_SCRIPT_B64}'))")
            + " "
            + shlex.quote(encoded)
        )
        argv = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10"]
        if self._workspace.port is not None:
            argv.extend(["-p", str(self._workspace.port)])
        argv.extend([self._workspace.target, command])
        env = {
            "PATH": os.environ.get("PATH", ""),
            "HOME": os.environ.get("HOME", ""),
            "SSH_AUTH_SOCK": os.environ.get("SSH_AUTH_SOCK", ""),
        }
        proc = subprocess.run(
            argv,
            env=env,
            capture_output=True,
            timeout=self._timeout + 15,
            check=False,
        )
        stdout = proc.stdout.decode("utf-8", errors="replace")[:_MAX_OUTPUT_BYTES]
        stderr = proc.stderr.decode("utf-8", errors="replace")[:_MAX_OUTPUT_BYTES]
        if proc.returncode != 0:
            raise RuntimeError(stderr or f"ssh exited {proc.returncode}")
        return stdout.rstrip("\n")


def resolve_workspace_tools(workspace_path: str) -> tuple[object, object, str]:
    remote = parse_ssh_workspace(workspace_path)
    if remote is not None:
        tool = SSHWorkspaceTool(remote)
        if not tool.probe():
            raise RuntimeError(f"SSH workspace unavailable: {remote.target}:{remote.root}")
        return tool, tool, f"ssh://{remote.target}{remote.root}"
    path = Path(workspace_path).expanduser()
    if not path.is_dir():
        raise RuntimeError(f"local workspace unavailable: {workspace_path}")
    from sonya.tools.code_tool import CodeTool

    return FilesystemTool(project_root=path), CodeTool(timeout_seconds=30, sandbox_dir=str(path)), str(path.resolve())


def probe_workspace(workspace_path: str) -> tuple[bool, str]:
    try:
        remote = parse_ssh_workspace(workspace_path)
        if remote is not None:
            ok = SSHWorkspaceTool(remote).probe()
            return ok, f"ssh://{remote.target}{remote.root}"
        path = Path(workspace_path).expanduser()
        return path.is_dir(), str(path)
    except Exception as err:
        return False, str(err)
