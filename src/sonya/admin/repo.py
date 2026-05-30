"""Repo management endpoints for the Atrium Console.

Lets Ivan inspect and control the Sonya git repo on the VPS from the Atrium
app — so if a selfmod (or anything) goes sideways he can commit / push / revert
without SSH.

Endpoints (all under /api/atrium/ → cookie-exempt, validate X-Atrium-Token):
  GET  /api/atrium/repo/status        → branch, ahead/behind, dirty files, recent log
  POST /api/atrium/repo/commit        {message} → stage -A + commit (Sonya identity)
  POST /api/atrium/repo/push          → push origin HEAD:branch (rebase-retry)
  POST /api/atrium/repo/revert        {mode, ref?} → discard / reset (DESTRUCTIVE)

revert modes:
  - "discard"        : git checkout -- . (drop unstaged working-tree changes)
  - "reset_hard"     : git reset --hard <ref|HEAD>   (HIGH RISK)
  - "reset_to_origin": git reset --hard origin/<branch> (match update.sh semantics)
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from aiohttp import web


def _project_root() -> Path:
    root = os.environ.get("SONYA_PROJECT_ROOT", "")
    if root:
        return Path(root)
    # admin/repo.py → src/sonya/admin → repo root is three parents up
    return Path(__file__).resolve().parent.parent.parent.parent


def _git_env() -> dict:
    env = {
        "GIT_AUTHOR_NAME": "Sonya",
        "GIT_AUTHOR_EMAIL": "sonya@local",
        "GIT_COMMITTER_NAME": "Sonya",
        "GIT_COMMITTER_EMAIL": "sonya@local",
    }
    for k in ("PATH", "HOME", "SSH_AUTH_SOCK", "GIT_SSH", "GIT_SSH_COMMAND"):
        if k in os.environ:
            env[k] = os.environ[k]
    return env


def _run(root: Path, *args: str, check: bool = False, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args],
        cwd=str(root),
        env=_git_env(),
        check=check,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _check_auth(request: web.Request) -> str | None:
    admin_password = request.app.get("admin_password", "")
    token = request.headers.get("X-Atrium-Token", "") or request.query.get("token", "")
    if admin_password and token != admin_password:
        return "auth"
    return None


def _cors(resp: web.Response) -> web.Response:
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Atrium-Token"
    return resp


async def repo_options(request: web.Request) -> web.Response:
    return _cors(web.Response(status=204))


async def repo_status(request: web.Request) -> web.Response:
    if (err := _check_auth(request)):
        return _cors(web.json_response({"error": err}, status=401))
    root = _project_root()
    try:
        branch = _run(root, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        porcelain = _run(root, "status", "--porcelain").stdout.strip()
        dirty = [ln for ln in porcelain.splitlines() if ln.strip()]
        # ahead/behind vs upstream
        ahead = behind = 0
        try:
            _run(root, "fetch", "origin", branch, timeout=30)
            counts = _run(root, "rev-list", "--left-right", "--count", f"origin/{branch}...HEAD").stdout.strip()
            if counts:
                parts = counts.split()
                if len(parts) == 2:
                    behind, ahead = int(parts[0]), int(parts[1])
        except Exception:
            pass
        log = _run(root, "log", "--oneline", "-12", "--no-decorate").stdout.strip().splitlines()
        return _cors(web.json_response({
            "ok": True,
            "root": str(root),
            "branch": branch,
            "ahead": ahead,
            "behind": behind,
            "dirty": dirty,
            "dirty_count": len(dirty),
            "log": log,
        }))
    except subprocess.TimeoutExpired:
        return _cors(web.json_response({"error": "git timeout"}, status=504))
    except Exception as e:
        return _cors(web.json_response({"error": f"{type(e).__name__}: {e}"}, status=500))


async def repo_commit(request: web.Request) -> web.Response:
    if (err := _check_auth(request)):
        return _cors(web.json_response({"error": err}, status=401))
    try:
        data = await request.json()
    except Exception:
        data = {}
    message = str(data.get("message") or "").strip()
    if not message:
        return _cors(web.json_response({"error": "message required"}, status=400))
    root = _project_root()
    try:
        branch = _run(root, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        if not branch or branch == "HEAD":
            return _cors(web.json_response({"error": "detached HEAD; refusing"}, status=409))
        _run(root, "add", "-A")
        status = _run(root, "status", "--porcelain").stdout.strip()
        if not status:
            return _cors(web.json_response({"ok": True, "note": "nothing to commit", "branch": branch}))
        commit = _run(root, "commit", "-m", message, "--no-verify")
        if commit.returncode != 0:
            return _cors(web.json_response(
                {"error": (commit.stderr or commit.stdout or "commit failed").strip()[:300]}, status=500))
        sha = _run(root, "rev-parse", "HEAD").stdout.strip()
        return _cors(web.json_response({"ok": True, "branch": branch, "commit_sha": sha[:12]}))
    except subprocess.TimeoutExpired:
        return _cors(web.json_response({"error": "git timeout"}, status=504))
    except Exception as e:
        return _cors(web.json_response({"error": f"{type(e).__name__}: {e}"}, status=500))


async def repo_push(request: web.Request) -> web.Response:
    if (err := _check_auth(request)):
        return _cors(web.json_response({"error": err}, status=401))
    root = _project_root()
    try:
        branch = _run(root, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        push = _run(root, "push", "origin", f"HEAD:{branch}", timeout=90)
        if push.returncode == 0:
            return _cors(web.json_response({"ok": True, "branch": branch}))
        err_text = (push.stderr or "") + (push.stdout or "")
        is_non_ff = any(s in err_text.lower() for s in ("non-fast-forward", "fetch first", "rejected"))
        if is_non_ff:
            _run(root, "fetch", "origin", branch, timeout=30)
            rebase = _run(root, "rebase", f"origin/{branch}", timeout=60)
            if rebase.returncode == 0:
                push2 = _run(root, "push", "origin", f"HEAD:{branch}", timeout=90)
                if push2.returncode == 0:
                    return _cors(web.json_response({"ok": True, "branch": branch, "rebased": True}))
                err_text = (push2.stderr or "") + (push2.stdout or "")
            else:
                _run(root, "rebase", "--abort", timeout=15)
                err_text = "rebase conflict: " + (rebase.stderr or rebase.stdout or "")
        return _cors(web.json_response({"error": err_text.strip()[:300]}, status=500))
    except subprocess.TimeoutExpired:
        return _cors(web.json_response({"error": "git timeout"}, status=504))
    except Exception as e:
        return _cors(web.json_response({"error": f"{type(e).__name__}: {e}"}, status=500))


async def repo_revert(request: web.Request) -> web.Response:
    if (err := _check_auth(request)):
        return _cors(web.json_response({"error": err}, status=401))
    try:
        data = await request.json()
    except Exception:
        data = {}
    mode = str(data.get("mode") or "").strip()
    ref = str(data.get("ref") or "HEAD").strip() or "HEAD"
    root = _project_root()
    try:
        branch = _run(root, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
        if mode == "discard":
            r = _run(root, "checkout", "--", ".")
            note = "discarded unstaged changes"
        elif mode == "reset_hard":
            r = _run(root, "reset", "--hard", ref)
            note = f"hard reset to {ref}"
        elif mode == "reset_to_origin":
            _run(root, "fetch", "origin", branch, timeout=30)
            r = _run(root, "reset", "--hard", f"origin/{branch}")
            note = f"hard reset to origin/{branch}"
        else:
            return _cors(web.json_response(
                {"error": "mode must be discard|reset_hard|reset_to_origin"}, status=400))
        if r.returncode != 0:
            return _cors(web.json_response(
                {"error": (r.stderr or r.stdout or "revert failed").strip()[:300]}, status=500))
        sha = _run(root, "rev-parse", "HEAD").stdout.strip()
        return _cors(web.json_response({"ok": True, "branch": branch, "note": note, "head": sha[:12]}))
    except subprocess.TimeoutExpired:
        return _cors(web.json_response({"error": "git timeout"}, status=504))
    except Exception as e:
        return _cors(web.json_response({"error": f"{type(e).__name__}: {e}"}, status=500))


def register_routes(app: web.Application) -> None:
    app.router.add_get("/api/atrium/repo/status", repo_status)
    app.router.add_post("/api/atrium/repo/commit", repo_commit)
    app.router.add_post("/api/atrium/repo/push", repo_push)
    app.router.add_post("/api/atrium/repo/revert", repo_revert)
    for path in (
        "/api/atrium/repo/status",
        "/api/atrium/repo/commit",
        "/api/atrium/repo/push",
        "/api/atrium/repo/revert",
    ):
        app.router.add_options(path, repo_options)
