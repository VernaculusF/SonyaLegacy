"""Sonya Admin Panel — local web UI.

Run: python -m sonya.admin
Opens on http://localhost:8877
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sonya.admin.static import ADMIN_HTML
from sonya.config import load_config, AppConfig
from sonya.memory.episodic import EpisodicMemory
from sonya.memory.semantic import SemanticMemory
from sonya.planning import build_full_context, plan_next
from sonya.planning.memory_wiring import record_response_as_memory
from sonya.runtime import WriteMaster
from sonya.state import ContinuityStream, Substrate, SubjectStateStore
from sonya.state.pending import PendingIntentionStore
from sonya.harness.audit import AuditLog

try:
    from aiohttp import web
    from aiohttp.web import middleware
except ImportError:
    raise ImportError("Install aiohttp: pip install aiohttp")

# Simple auth
_ADMIN_PASSWORD = None  # Set via env SONYA_ADMIN_PASSWORD


@middleware
async def auth_middleware(request: web.Request, handler):
    password = request.app.get("admin_password")
    if not password:
        return await handler(request)
    # Atrium endpoints use their own header-based auth (X-Atrium-Token).
    # Skip cookie check here; the handler validates the header itself.
    # См. docs/atrium/CHANNELS.md §3.2.
    if request.path == "/atrium/feed" or request.path.startswith("/api/atrium/"):
        return await handler(request)
    # Check cookie
    if request.cookies.get("sonya_auth") == password:
        return await handler(request)
    # Check if this is login page
    if request.path == "/login":
        return await handler(request)
    # Redirect to login
    return web.HTTPFound("/login")


def _get_substrate(config: AppConfig) -> Substrate:
    """Open substrate. Read-only if core process is running (avoids write race)."""
    core_running = WriteMaster.is_held(config.substrate_path)
    return Substrate.open(config.substrate_path, read_only=core_running)


def _get_substrate_writable(config: AppConfig) -> Substrate:
    """Open substrate writable regardless of core status.

    Safe for short admin transactions — SQLite WAL mode handles concurrent
    writers via brief row-level locking. Core re-reads provider_keys on every
    `acquire()`, so admin changes (status flips, adds, deletes) are visible
    immediately without core restart.
    """
    return Substrate.open(config.substrate_path, read_only=False)


def _is_core_running(config: AppConfig) -> bool:
    return WriteMaster.is_held(config.substrate_path)


async def handle_index(request: web.Request) -> web.Response:
    return web.Response(text=ADMIN_HTML, content_type="text/html")


async def handle_login(request: web.Request) -> web.Response:
    if request.method == "POST":
        data = await request.post()
        pwd = data.get("password", "")
        if pwd == request.app.get("admin_password"):
            resp = web.HTTPFound("/")
            resp.set_cookie("sonya_auth", pwd, max_age=86400 * 30)
            return resp
        return web.Response(text=_LOGIN_HTML.replace("{{error}}", "Wrong password"), content_type="text/html")
    return web.Response(text=_LOGIN_HTML.replace("{{error}}", ""), content_type="text/html")


_LOGIN_HTML = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>Sonya Login</title>
<style>body{font-family:sans-serif;background:#0d1117;color:#c9d1d9;display:flex;align-items:center;justify-content:center;height:100vh}
.box{background:#161b22;border:1px solid #30363d;border-radius:12px;padding:40px;width:300px;text-align:center}
h1{color:#f0f;margin-bottom:20px}input{width:100%;padding:12px;background:#0d1117;border:1px solid #30363d;border-radius:6px;color:#c9d1d9;margin:10px 0;font-size:14px}
button{width:100%;padding:12px;background:#f0f;color:#0d1117;border:none;border-radius:6px;font-weight:bold;cursor:pointer;font-size:14px}
.err{color:#f66;font-size:12px}</style></head>
<body><div class="box"><h1>Sonya</h1><form method="POST"><input type="password" name="password" placeholder="Password" autofocus><button>Enter</button></form><p class="err">{{error}}</p></div></body></html>"""


async def api_dashboard(request: web.Request) -> web.Response:
    config = request.app["config"]
    sub = _get_substrate(config)
    try:
        state = SubjectStateStore(sub).load()
        latest_seq = ContinuityStream(sub).latest_seq()
        return web.json_response({
            "state": {
                "active_principal": state.active_principal_id,
                "emotional_vector": state.emotional_vector,
                "drift_signals": list(state.drift_signals),
                "pending_intentions": list(state.pending_intentions),
            },
            "latest_seq": latest_seq,
            "config": {
                "llm_api_base": config.llm_api_base,
                "llm_model": config.llm_model,
                "substrate_path": str(config.substrate_path),
            },
        })
    finally:
        sub.close()


async def api_thoughts(request: web.Request) -> web.Response:
    config = request.app["config"]
    # Optional: limit, kinds filter, since seq.
    try:
        limit = int(request.query.get("limit", "100"))
    except ValueError:
        limit = 100
    limit = max(1, min(500, limit))
    kinds_raw = request.query.get("kinds", "").strip()
    kinds_filter = {k for k in kinds_raw.split(",") if k} or None
    sub = _get_substrate(config)
    try:
        stream = ContinuityStream(sub)
        latest = stream.latest_seq()
        # Pull a wider window than `limit` so filter has things to choose from
        window = max(limit * 3, 200)
        start = max(0, latest - window)
        events = list(stream.read_since(start))
        if kinds_filter:
            events = [e for e in events if e.kind in kinds_filter]
        events = events[-limit:]
        return web.json_response({
            "latest_seq": latest,
            "kinds_filter": sorted(kinds_filter) if kinds_filter else None,
            "events": [
                {"seq": e.seq, "kind": e.kind, "payload": e.payload, "created_at": e.created_at}
                for e in reversed(events)
            ]
        })
    finally:
        sub.close()


async def api_memory(request: web.Request) -> web.Response:
    config = request.app["config"]
    sub = _get_substrate(config)
    try:
        episodic = EpisodicMemory(sub)
        semantic = SemanticMemory(sub)
        recent = episodic.get_recent(limit=30, mark_accessed=False)
        facts = semantic.get_all(limit=20)
        # Embedding index status (graceful if fastembed not installed)
        try:
            from sonya.memory.embedder import Embedder
            from sonya.memory.recall import RecallStore
            if Embedder.is_available():
                rs = RecallStore(sub)
                embedding_index = {
                    "available": True,
                    "indexed": rs.count_indexed(),
                    "pending": rs.count_pending(),
                }
            else:
                embedding_index = {"available": False}
        except Exception as exc:
            embedding_index = {"available": False, "error": str(exc)}
        return web.json_response({
            "episodic": [
                {"event_type": e.event_type, "timestamp": e.timestamp,
                 "raw_content": e.raw_content, "importance_score": e.importance_score,
                 "retention_strength": e.retention_strength}
                for e in recent
            ],
            "semantic": [
                {"fact_type": f.fact_type, "statement": f.statement, "confidence": f.confidence}
                for f in facts
            ],
            "embedding_index": embedding_index,
        })
    finally:
        sub.close()


async def api_chat_send(request: web.Request) -> web.Response:
    config = request.app["config"]
    data = await request.json()
    message = data.get("message", "")
    if not message:
        return web.json_response({"response": ""})

    # Refuse writes from admin if core is running — avoids substrate race
    if _is_core_running(config):
        return web.json_response(
            {
                "response": "",
                "error": "core_running",
                "detail": "Stop the core process first (admin panel → Core → Stop) "
                          "to chat from admin. Otherwise message goes through telegram.",
            },
            status=409,
        )

    sub = _get_substrate(config)
    try:
        ctx = build_full_context(substrate=sub, user_input=message, principal_id="ivan")

        api_key_secret = config.openrouter_api_key
        api_key = api_key_secret.get_secret_value() if api_key_secret else ""

        import httpx

        class _Provider:
            async def complete_text(self, messages, **kwargs):
                headers: dict[str, str] = {"Content-Type": "application/json"}
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
                async with httpx.AsyncClient(timeout=60.0, verify=False) as client:
                    resp = await client.post(
                        f"{config.llm_api_base}/chat/completions",
                        headers=headers,
                        json={"model": config.llm_model, "messages": messages, "max_tokens": 1000, "temperature": 0.8, "stream": False},
                    )
                    resp.raise_for_status()
                    # Handle potential streaming response (multiple JSON objects)
                    text = resp.text.strip()
                    import json as _json
                    try:
                        data = _json.loads(text)
                    except _json.JSONDecodeError:
                        first_line = text.split("\n", 1)[0].strip()
                        data = _json.loads(first_line)
                    return data["choices"][0]["message"]["content"]

        response = await plan_next(ctx, _Provider(), purpose="admin_chat")
        record_response_as_memory(sub, message, response, channel="admin")
        return web.json_response({"response": response.text})
    finally:
        sub.close()


async def api_telegram(request: web.Request) -> web.Response:
    """Return recent telegram messages from continuity stream."""
    config = request.app["config"]
    sub = _get_substrate(config)
    try:
        stream = ContinuityStream(sub)
        latest = stream.latest_seq()
        events = list(stream.read_since(max(0, latest - 200)))
        tg_events = [e for e in events if "telegram" in e.kind or "incoming" in e.kind][-50:]
        return web.json_response({
            "messages": [
                {
                    "chat_id": e.payload.get("chat_id", ""),
                    "sender_id": e.payload.get("sender_id", ""),
                    "text": e.payload.get("text", ""),
                    "is_private": e.payload.get("is_private", False),
                    "date": e.created_at[:19],
                }
                for e in reversed(tg_events)
            ]
        })
    finally:
        sub.close()


async def api_audit(request: web.Request) -> web.Response:
    config = request.app["config"]
    sub = _get_substrate(config)
    try:
        audit = AuditLog(sub)
        entries = audit.query()[-30:]
        return web.json_response({
            "entries": [
                {"seq": e.seq, "timestamp": e.timestamp, "action": e.action,
                 "decision": e.decision, "scope": e.scope}
                for e in reversed(entries)
            ]
        })
    finally:
        sub.close()


async def api_substrate(request: web.Request) -> web.Response:
    config = request.app["config"]
    sub = _get_substrate(config)
    try:
        tables = sub.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_info = []
        for (name,) in tables:
            count = sub.connection.execute(f"SELECT COUNT(*) FROM [{name}]").fetchone()[0]
            table_info.append({"name": name, "rows": count})
        return web.json_response({
            "version": sub.schema_version,
            "path": str(config.substrate_path),
            "tables": table_info,
        })
    finally:
        sub.close()


# --- Self-modification proposals ---


async def api_selfmod_list(request: web.Request) -> web.Response:
    """List all self-modification proposals (read-only — admin can read while core runs)."""
    config = request.app["config"]
    status_filter = request.query.get("status", "")
    sub = _get_substrate(config)
    try:
        from sonya.selfmod import ProposalStatus, ProposalStore
        store = ProposalStore(sub)
        if status_filter:
            try:
                status = ProposalStatus(status_filter)
                proposals = store.list_by_status(status)
            except ValueError:
                return web.json_response({"error": f"unknown status: {status_filter}"}, status=400)
        else:
            proposals = []
            for s in ProposalStatus:
                proposals.extend(store.list_by_status(s))
            proposals.sort(key=lambda p: p.created_at, reverse=True)
            proposals = proposals[:100]

        return web.json_response({
            "count": len(proposals),
            "proposals": [
                {
                    "proposal_id": p.proposal_id,
                    "target_module": p.target_module,
                    "summary": p.change_summary,
                    "status": p.status.value,
                    "proposed_by": p.proposed_by_principal_id,
                    "created_at": p.created_at,
                    "updated_at": p.updated_at,
                }
                for p in proposals
            ],
        })
    finally:
        sub.close()


async def api_selfmod_get(request: web.Request) -> web.Response:
    """Get full proposal details including diff_blob."""
    config = request.app["config"]
    proposal_id = request.match_info.get("proposal_id", "")
    sub = _get_substrate(config)
    try:
        from sonya.selfmod import ProposalStore
        from sonya.selfmod.proposal import ProposalNotFoundError
        store = ProposalStore(sub)
        try:
            p = store.get(proposal_id)
        except ProposalNotFoundError:
            return web.json_response({"error": "not found"}, status=404)
        return web.json_response({
            "proposal_id": p.proposal_id,
            "target_module": p.target_module,
            "summary": p.change_summary,
            "diff_blob": p.diff_blob,
            "status": p.status.value,
            "proposed_by": p.proposed_by_principal_id,
            "created_at": p.created_at,
            "updated_at": p.updated_at,
        })
    finally:
        sub.close()


async def api_selfmod_approve(request: web.Request) -> web.Response:
    """Primary anchor (Ivan) approves a REQUIRES_GOVERNED_CHANGE proposal.

    No core-running gate — SQLite WAL handles concurrent writes. Core
    reads proposal status fresh on the next selfmod cycle.
    """
    config = request.app["config"]
    proposal_id = request.match_info.get("proposal_id", "")

    sub = _get_substrate_writable(config)
    try:
        from sonya.harness.approval import ApprovalManager
        from sonya.selfmod import ProposalStore
        from sonya.selfmod.proposal import ProposalNotFoundError, ProposalStatus

        store = ProposalStore(sub)
        try:
            p = store.get(proposal_id)
        except ProposalNotFoundError:
            return web.json_response({"error": "not found"}, status=404)

        if p.status != ProposalStatus.REQUIRES_GOVERNED_CHANGE:
            return web.json_response({
                "error": f"proposal status is {p.status.value}, expected requires_governed_change",
            }, status=400)

        # Find the associated approval request and approve it
        approvals = ApprovalManager(sub)
        reqs = approvals.find_by_action_pattern(f"%{proposal_id}%")
        if not reqs:
            # No approval request exists yet (Sonya hasn't called selfmod.governed).
            # For Ivan's manual approval through admin, we create + approve in one shot —
            # admin UI is a trusted authority path, no need for two-step dance.
            req = approvals.create(
                principal_id="sonya",
                action=f"selfmod.governed:{proposal_id}",
                scope=f"selfmod.{p.target_module}",
            )
            approvals.approve(req.request_id, by_principal_id="ivan")
            store.update_status(proposal_id, ProposalStatus.GOVERNED_APPROVED)
            return web.json_response({
                "status": "approved",
                "proposal_id": proposal_id,
                "approval_request_id": req.request_id,
                "note": "auto-created approval request (admin shortcut)",
            })

        target_req = next((r for r in reqs if r.status.value == "pending"), None)
        if target_req is None:
            return web.json_response({"error": "no pending request"}, status=400)

        approvals.approve(target_req.request_id, by_principal_id="ivan")
        # Update proposal status
        store.update_status(proposal_id, ProposalStatus.GOVERNED_APPROVED)

        return web.json_response({
            "status": "approved",
            "proposal_id": proposal_id,
            "approval_request_id": target_req.request_id,
        })
    finally:
        sub.close()


async def api_selfmod_deny(request: web.Request) -> web.Response:
    """Primary anchor denies a proposal."""
    config = request.app["config"]
    proposal_id = request.match_info.get("proposal_id", "")

    sub = _get_substrate_writable(config)
    try:
        from sonya.harness.approval import ApprovalManager
        from sonya.selfmod import ProposalStore
        from sonya.selfmod.proposal import ProposalNotFoundError, ProposalStatus

        store = ProposalStore(sub)
        try:
            p = store.get(proposal_id)
        except ProposalNotFoundError:
            return web.json_response({"error": "not found"}, status=404)

        approvals = ApprovalManager(sub)
        reqs = approvals.find_by_action_pattern(f"%{proposal_id}%")
        target_req = next((r for r in reqs if r.status.value == "pending"), None)
        if target_req:
            approvals.deny(target_req.request_id, by_principal_id="ivan")

        store.update_status(proposal_id, ProposalStatus.REJECTED)
        return web.json_response({"status": "rejected", "proposal_id": proposal_id})
    finally:
        sub.close()


# --- Core process management ---

_core_process: Any = None
_core_log_file: Any = None  # tracked to close properly


def _project_paths():
    """Return (project_root, venv_python, log_path) from env or sensible defaults."""
    import os
    project_root = os.environ.get("SONYA_PROJECT_ROOT", os.path.expanduser("~/Sonya"))
    venv_python = os.environ.get(
        "SONYA_VENV_PYTHON",
        os.path.join(project_root, ".venv", "bin", "python"),
    )
    log_path = os.environ.get("SONYA_CORE_LOG_PATH", "/tmp/sonya.log")
    return project_root, venv_python, log_path


async def api_core_status(request: web.Request) -> web.Response:
    """Check if core process is running.

    Truth source is the WriteMaster lock on substrate — that's held by whichever
    process opened substrate read-write (admin-started subprocess, systemd unit,
    or manual launch). The legacy `_core_process` global is checked too so the
    PID is shown when admin owns the process.
    """
    global _core_process

    config = load_config()
    running = _is_core_running(config)
    pid = _core_process.pid if (
        _core_process is not None and _core_process.returncode is None
    ) else None
    return web.json_response({"running": running, "pid": pid})


async def api_core_start(request: web.Request) -> web.Response:
    """Start the core process (sonya main with userbot + thinking).

    Query params:
      mode = full | telegram_only | thinking_only (default: full)
    """
    import subprocess
    import os
    global _core_process, _core_log_file

    # Check if already running
    if _core_process is not None and _core_process.returncode is None:
        return web.json_response({"status": "already_running", "pid": _core_process.pid})

    # Also refuse if some other process (systemd / manual) holds the substrate
    # write lock — admin-spawned core would crash on WriteMasterContention.
    config = load_config()
    if _is_core_running(config):
        return web.json_response(
            {"status": "already_running_external",
             "message": "Core is already running outside admin (systemd or manual). "
                        "Use systemctl to manage it, or stop it first."},
            status=409,
        )

    mode = request.query.get("mode", "full")
    project_root, venv_python, log_path = _project_paths()

    # Build env with PYTHONPATH and toggles
    env = os.environ.copy()
    env["PYTHONPATH"] = f"{project_root}/src:{project_root}/packages/tg-userbot/src"

    if mode == "telegram_only":
        env["SONYA_ENABLE_TELEGRAM"] = "1"
        env["SONYA_ENABLE_THINKING"] = "0"
    elif mode == "thinking_only":
        env["SONYA_ENABLE_TELEGRAM"] = "0"
        env["SONYA_ENABLE_THINKING"] = "1"
    else:  # full
        env["SONYA_ENABLE_TELEGRAM"] = "1"
        env["SONYA_ENABLE_THINKING"] = "1"

    # Close any previous log file handle
    if _core_log_file is not None and not _core_log_file.closed:
        try:
            _core_log_file.close()
        except Exception:
            pass

    _core_log_file = open(log_path, "w")

    # Start core as subprocess
    _core_process = subprocess.Popen(
        [venv_python, "-m", "sonya"],
        cwd=project_root,
        env=env,
        stdout=_core_log_file,
        stderr=subprocess.STDOUT,
    )
    return web.json_response({"status": "started", "pid": _core_process.pid, "mode": mode})


async def api_core_stop(request: web.Request) -> web.Response:
    """Stop the core process.

    Two paths:
    1. If admin started the process via api_core_start → SIGTERM/SIGKILL it directly.
    2. If process was started externally (systemd) → use systemctl stop.

    Truth source for "is running" is WriteMaster lock on substrate, not _core_process.
    """
    import signal
    import asyncio
    import subprocess
    global _core_process, _core_log_file

    config = request.app["config"]

    # Path 1: admin-managed subprocess
    if _core_process is not None and _core_process.returncode is None:
        pid = _core_process.pid
        proc = _core_process
        try:
            proc.send_signal(signal.SIGTERM)
        except ProcessLookupError:
            _core_process = None
            return web.json_response({"status": "already_dead", "pid": pid})

        for _ in range(20):
            await asyncio.sleep(0.5)
            if proc.poll() is not None:
                break

        method = "sigterm"
        if proc.poll() is None:
            try:
                proc.send_signal(signal.SIGKILL)
                proc.wait(timeout=3)
            except ProcessLookupError:
                pass
            method = "sigkill"

        _core_process = None
        if _core_log_file is not None and not _core_log_file.closed:
            try:
                _core_log_file.close()
            except Exception:
                pass
            _core_log_file = None

        return web.json_response({"status": "stopped", "pid": pid, "method": method})

    # Path 2: externally-managed (systemd). Try systemctl stop.
    if _is_core_running(config):
        try:
            # Try user systemd first, then system
            result = subprocess.run(
                ["systemctl", "--user", "stop", "sonya"],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0:
                # Wait for write-master release
                for _ in range(20):
                    await asyncio.sleep(0.5)
                    if not _is_core_running(config):
                        break
                return web.json_response({"status": "stopped", "method": "systemctl --user"})
            # Fallback to system-level systemctl (requires sudo, may fail)
            result = subprocess.run(
                ["sudo", "-n", "systemctl", "stop", "sonya"],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0:
                for _ in range(20):
                    await asyncio.sleep(0.5)
                    if not _is_core_running(config):
                        break
                return web.json_response({"status": "stopped", "method": "sudo systemctl"})
            return web.json_response({
                "status": "error",
                "error": "systemctl stop failed (no permission?)",
                "user_stderr": result.stderr[:300],
            }, status=500)
        except subprocess.TimeoutExpired:
            return web.json_response({
                "status": "error",
                "error": "systemctl stop timed out",
            }, status=500)
        except FileNotFoundError:
            return web.json_response({
                "status": "error",
                "error": "systemctl not available",
            }, status=500)

    return web.json_response({"status": "not_running"})


async def api_core_logs(request: web.Request) -> web.Response:
    """Get last N lines of core log."""
    import os
    lines = int(request.query.get("lines", "50"))
    _, _, log_path = _project_paths()
    if not os.path.exists(log_path):
        return web.json_response({"logs": ""})
    with open(log_path, "r", encoding="utf-8", errors="replace") as f:
        all_lines = f.readlines()
    return web.json_response({"logs": "".join(all_lines[-lines:])})


# ============================================================
# Providers (own key pool, replacing OmniRoute)
# ============================================================

def _mask_key(s: str) -> str:
    if not s:
        return ""
    if len(s) <= 12:
        return "***"
    return s[:6] + "..." + s[-4:]


async def api_providers_get(request: web.Request) -> web.Response:
    """List provider settings + all keys (masked)."""
    from sonya.providers import KeyStore
    config = request.app["config"]
    sub = _get_substrate(config)
    try:
        store = KeyStore(sub)
        settings = store.get_settings()
        keys = store.list_keys()
        return web.json_response({
            "settings": {
                "active_provider": settings.active_provider,
                "default_model": settings.default_model,
                "default_base_url": settings.default_base_url,
                "updated_at": settings.updated_at,
            },
            "keys": [
                {
                    "key_id": k.key_id,
                    "provider": k.provider,
                    "name": k.name,
                    "key_masked": _mask_key(k.api_key),
                    "base_url": k.base_url,
                    "model": k.model,
                    "slot": k.slot,
                    "status": k.status.value,
                    "priority": k.priority,
                    "cooldown_until": k.cooldown_until,
                    "last_used_at": k.last_used_at,
                    "last_error": k.last_error,
                    "last_error_at": k.last_error_at,
                    "request_count": k.request_count,
                    "success_count": k.success_count,
                    "error_count": k.error_count,
                    "created_at": k.created_at,
                    "updated_at": k.updated_at,
                    "account_id": k.account_id,
                    "balance": k.balance(),
                    "balance_checked_at": k.balance_checked_at,
                }
                for k in keys
            ],
        })
    finally:
        sub.close()


async def api_approvals_get(request: web.Request) -> web.Response:
    """List all pending approval requests (shell.run, pip.install, selfmod.governed).

    Read-only; safe to call while core is running.
    """
    from sonya.harness.approval import ApprovalManager

    config = request.app["config"]
    sub = _get_substrate(config)
    try:
        mgr = ApprovalManager(sub)
        pending = mgr.list_pending()
        return web.json_response({
            "count": len(pending),
            "requests": [
                {
                    "request_id": r.request_id,
                    "principal_id": r.principal_id,
                    "action": r.action,
                    "scope": r.scope,
                    "status": r.status.value,
                    "created_at": r.created_at,
                }
                for r in pending
            ],
        })
    finally:
        sub.close()


async def api_approvals_decide(request: web.Request) -> web.Response:
    """Approve or deny a pending approval request.

    Path: /api/approvals/{request_id}/{approve|deny}
    Decision is recorded under principal_id="ivan". Core sees it on next
    poll inside the gated tool (already implemented in shell_tool/pip_tool).
    """
    from sonya.harness.approval import (
        ApprovalAlreadyDecidedError,
        ApprovalManager,
        ApprovalNotFoundError,
    )

    request_id = request.match_info["request_id"]
    decision = request.match_info["decision"]
    if decision not in ("approve", "deny"):
        return web.json_response({"error": "decision must be approve or deny"}, status=400)

    config = request.app["config"]
    sub = _get_substrate_writable(config)
    try:
        mgr = ApprovalManager(sub)
        try:
            if decision == "approve":
                req = mgr.approve(request_id, by_principal_id="ivan")
            else:
                req = mgr.deny(request_id, by_principal_id="ivan")
        except ApprovalNotFoundError:
            return web.json_response({"error": "not found"}, status=404)
        except ApprovalAlreadyDecidedError as exc:
            return web.json_response({"error": str(exc)}, status=409)
        return web.json_response({
            "status": req.status.value,
            "request_id": req.request_id,
            "decided_at": req.decided_at,
            "decided_by_principal_id": req.decided_by_principal_id,
        })
    finally:
        sub.close()


async def api_providers_balance_refresh(request: web.Request) -> web.Response:
    """Force refresh balance for one key (or all active fireworks keys if no key_id).

    Inline call to fireworks API; returns the fresh snapshot. Admin can press
    a button to refresh without waiting for the periodic 10-min loop.
    """
    from sonya.providers import KeyStore, KeyStatus
    from sonya.providers.fireworks_balance import fetch_fireworks_balance

    config = request.app["config"]
    sub = _get_substrate_writable(config)
    try:
        store = KeyStore(sub)
        target_key_id = request.match_info.get("key_id")
        if target_key_id:
            k = store.get_key(target_key_id)
            if k is None:
                return web.json_response({"error": "not found"}, status=404)
            keys = [k]
        else:
            keys = [k for k in store.list_keys("fireworks") if k.status is KeyStatus.ACTIVE]
        results = []
        for k in keys:
            if k.provider != "fireworks":
                results.append({"key_id": k.key_id, "skipped": "provider not supported"})
                continue
            snap = await fetch_fireworks_balance(k.api_key)
            store.update_balance(
                k.key_id,
                account_id=snap.get("account_id", "") or k.account_id,
                balance=snap,
            )
            results.append({"key_id": k.key_id, "balance": snap})
        return web.json_response({"refreshed": len(results), "results": results})
    finally:
        sub.close()


async def api_providers_settings(request: web.Request) -> web.Response:
    """Update provider settings (active_provider, default_model, default_base_url).

    No core-running gate — SQLite WAL handles concurrent admin writes safely.
    Core re-reads settings on every LLM call.
    """
    from sonya.providers import KeyStore
    config = request.app["config"]
    data = await request.json()
    sub = _get_substrate_writable(config)
    try:
        store = KeyStore(sub)
        settings = store.set_settings(
            active_provider=data.get("active_provider"),
            default_model=data.get("default_model"),
            default_base_url=data.get("default_base_url"),
        )
        return web.json_response({
            "status": "updated",
            "settings": {
                "active_provider": settings.active_provider,
                "default_model": settings.default_model,
                "default_base_url": settings.default_base_url,
            },
        })
    finally:
        sub.close()


async def api_providers_keys_add(request: web.Request) -> web.Response:
    """Add a new key. Body: {provider, name, api_key, base_url?, model?, priority?, slot?}"""
    from sonya.providers import KeyStore
    config = request.app["config"]
    data = await request.json()
    required = ("provider", "name", "api_key")
    for f in required:
        if not str(data.get(f, "")).strip():
            return web.json_response({"error": f"missing required field: {f}"}, status=400)
    sub = _get_substrate_writable(config)
    try:
        store = KeyStore(sub)
        # Default base_url per provider
        base_url = data.get("base_url") or _default_base_url(data["provider"])
        key = store.add_key(
            provider=data["provider"].strip(),
            name=data["name"].strip(),
            api_key=data["api_key"].strip(),
            base_url=base_url,
            model=(data.get("model") or "").strip(),
            priority=int(data.get("priority") or 0),
            slot=(data.get("slot") or "text").strip(),
        )
        return web.json_response({"status": "added", "key_id": key.key_id})
    finally:
        sub.close()


def _default_base_url(provider: str) -> str:
    return {
        "fireworks": "https://api.fireworks.ai/inference/v1",
        "openrouter": "https://openrouter.ai/api/v1",
        "groq": "https://api.groq.com/openai/v1",
        "deepinfra": "https://api.deepinfra.com/v1/openai",
        "together": "https://api.together.xyz/v1",
        "cerebras": "https://api.cerebras.ai/v1",
        "anthropic": "https://api.anthropic.com/v1",
        "openai": "https://api.openai.com/v1",
        "google": "https://generativelanguage.googleapis.com/v1beta/openai",
        # Local omniroute proxy on VPS — routes kr/* models through bundled
        # Kiro OAuth pool (11 accounts) inside the docker container. Sonya
        # uses this as a paid-quality fallback when fireworks slots are
        # cooled down or for code/critical purposes that benefit from
        # Sonnet-class quality.
        "kr": "http://127.0.0.1:20128/v1",
    }.get(provider.lower(), "")


async def api_providers_keys_update(request: web.Request) -> web.Response:
    """Update a key's metadata. Body any of: name, base_url, model, priority, slot"""
    from sonya.providers import KeyStore
    config = request.app["config"]
    key_id = request.match_info["key_id"]
    data = await request.json()
    sub = _get_substrate_writable(config)
    try:
        store = KeyStore(sub)
        if not store.get_key(key_id):
            return web.json_response({"error": "not found"}, status=404)
        store.update_metadata(
            key_id,
            name=data.get("name"),
            base_url=data.get("base_url"),
            model=data.get("model"),
            priority=int(data["priority"]) if "priority" in data else None,
            slot=data.get("slot"),
        )
        return web.json_response({"status": "updated"})
    finally:
        sub.close()


async def api_providers_keys_delete(request: web.Request) -> web.Response:
    from sonya.providers import KeyStore
    config = request.app["config"]
    key_id = request.match_info["key_id"]
    sub = _get_substrate_writable(config)
    try:
        store = KeyStore(sub)
        if not store.get_key(key_id):
            return web.json_response({"error": "not found"}, status=404)
        store.delete_key(key_id)
        return web.json_response({"status": "deleted"})
    finally:
        sub.close()


async def api_providers_keys_status(request: web.Request) -> web.Response:
    """Set status manually: active / disabled / banned"""
    from sonya.providers import KeyStatus, KeyStore
    config = request.app["config"]
    key_id = request.match_info["key_id"]
    data = await request.json()
    raw = (data.get("status") or "").strip().lower()
    if raw not in {"active", "disabled", "banned"}:
        return web.json_response({"error": "status must be active/disabled/banned"}, status=400)
    sub = _get_substrate_writable(config)
    try:
        store = KeyStore(sub)
        if not store.get_key(key_id):
            return web.json_response({"error": "not found"}, status=404)
        store.update_status(key_id, KeyStatus(raw))
        return web.json_response({"status": "updated", "new_status": raw})
    finally:
        sub.close()


async def api_providers_keys_test(request: web.Request) -> web.Response:
    """Test a key by making a real /chat/completions call.

    Works whether or not core is running — opens substrate read-only and
    issues a one-off HTTP request without touching key counters.
    """
    import httpx
    from sonya.providers import KeyStore
    config = request.app["config"]
    key_id = request.match_info["key_id"]
    sub = _get_substrate(config)
    try:
        store = KeyStore(sub)
        key = store.get_key(key_id)
        if key is None:
            return web.json_response({"error": "not found"}, status=404)
        settings = store.get_settings()
        model = key.model or settings.default_model
        base_url = key.base_url or settings.default_base_url
        url = f"{base_url.rstrip('/')}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {key.api_key}",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": "Reply with exactly: pong"},
            ],
            "max_tokens": 8,
            "temperature": 0,
            "stream": False,
        }
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=5.0)) as client:
                resp = await client.post(url, headers=headers, json=payload)
            ok = 200 <= resp.status_code < 300
            text_preview = resp.text[:200]
            return web.json_response({
                "ok": ok,
                "status_code": resp.status_code,
                "response_preview": text_preview,
                "model_used": model,
                "base_url": base_url,
            })
        except Exception as err:
            return web.json_response({
                "ok": False,
                "error": f"{type(err).__name__}: {err}",
            })
    finally:
        sub.close()


# ============================================================
# LLM call audit (token usage)
# ============================================================

async def api_llm_calls(request: web.Request) -> web.Response:
    """Recent LLM calls + per-purpose / per-model totals."""
    config = request.app["config"]
    sub = _get_substrate(config)
    try:
        limit = int(request.query.get("limit", "100"))
        rows = sub.connection.execute(
            "SELECT call_id, timestamp, key_id, provider, model, purpose, "
            "prompt_tokens, completion_tokens, total_tokens, latency_ms, "
            "status, http_status, error "
            "FROM llm_calls ORDER BY call_id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        recent = [
            {
                "call_id": r[0],
                "timestamp": r[1],
                "key_id": r[2],
                "provider": r[3],
                "model": r[4],
                "purpose": r[5],
                "prompt_tokens": r[6],
                "completion_tokens": r[7],
                "total_tokens": r[8],
                "latency_ms": r[9],
                "status": r[10],
                "http_status": r[11],
                "error": r[12],
            }
            for r in rows
        ]

        # Aggregate stats — last 24h, last hour, all-time totals
        agg_24h = sub.connection.execute(
            "SELECT COUNT(*), COALESCE(SUM(prompt_tokens),0), COALESCE(SUM(completion_tokens),0), "
            "COALESCE(SUM(total_tokens),0) "
            "FROM llm_calls WHERE timestamp > datetime('now','-1 day') AND status='ok'"
        ).fetchone()
        agg_1h = sub.connection.execute(
            "SELECT COUNT(*), COALESCE(SUM(prompt_tokens),0), COALESCE(SUM(completion_tokens),0), "
            "COALESCE(SUM(total_tokens),0) "
            "FROM llm_calls WHERE timestamp > datetime('now','-1 hour') AND status='ok'"
        ).fetchone()
        agg_total = sub.connection.execute(
            "SELECT COUNT(*), COALESCE(SUM(prompt_tokens),0), COALESCE(SUM(completion_tokens),0), "
            "COALESCE(SUM(total_tokens),0) "
            "FROM llm_calls WHERE status='ok'"
        ).fetchone()

        by_purpose = sub.connection.execute(
            "SELECT purpose, COUNT(*), COALESCE(SUM(total_tokens),0) "
            "FROM llm_calls WHERE timestamp > datetime('now','-1 day') AND status='ok' "
            "GROUP BY purpose ORDER BY 3 DESC"
        ).fetchall()

        by_model = sub.connection.execute(
            "SELECT model, COUNT(*), COALESCE(SUM(total_tokens),0) "
            "FROM llm_calls WHERE timestamp > datetime('now','-1 day') AND status='ok' "
            "GROUP BY model ORDER BY 3 DESC"
        ).fetchall()

        errors_24h = sub.connection.execute(
            "SELECT COUNT(*) FROM llm_calls "
            "WHERE timestamp > datetime('now','-1 day') AND status != 'ok'"
        ).fetchone()[0]

        return web.json_response({
            "totals": {
                "all_time": {"calls": agg_total[0], "prompt_tokens": agg_total[1],
                             "completion_tokens": agg_total[2], "total_tokens": agg_total[3]},
                "last_24h": {"calls": agg_24h[0], "prompt_tokens": agg_24h[1],
                             "completion_tokens": agg_24h[2], "total_tokens": agg_24h[3]},
                "last_1h": {"calls": agg_1h[0], "prompt_tokens": agg_1h[1],
                            "completion_tokens": agg_1h[2], "total_tokens": agg_1h[3]},
                "errors_24h": errors_24h,
            },
            "by_purpose_24h": [
                {"purpose": r[0], "calls": r[1], "tokens": r[2]} for r in by_purpose
            ],
            "by_model_24h": [
                {"model": r[0], "calls": r[1], "tokens": r[2]} for r in by_model
            ],
            "recent": recent,
        })
    finally:
        sub.close()


# ============================================================
# Tasks (admin view of task runtime)
# ============================================================

async def api_tasks(request: web.Request) -> web.Response:
    """List recent tasks with full state."""
    from sonya.tasks.store import TaskStore
    config = request.app["config"]
    sub = _get_substrate(config)
    try:
        store = TaskStore(sub)
        tasks = store.list_all(limit=100)
        return web.json_response({
            "tasks": [
                {
                    "task_id": t.task_id,
                    "title": t.title,
                    "description": t.description,
                    "status": t.status.value,
                    "created_by": t.created_by,
                    "scheduled_for": t.scheduled_for,
                    "notify_mode": t.notify_mode,
                    "plan_steps": t.plan_steps,
                    "completed_count": len(t.completed_steps),
                    "total_steps": len(t.plan_steps),
                    "sessions_used": t.sessions_used,
                    "max_sessions": t.max_sessions,
                    "next_step_hint": t.next_step_hint,
                    "last_session_notes": t.last_session_notes[:300],
                    "blocker": t.blocker,
                    "result": t.result[:300],
                    "principal_id": t.principal_id,
                    "created_at": t.created_at,
                    "updated_at": t.updated_at,
                }
                for t in tasks
            ]
        })
    finally:
        sub.close()


async def api_tasks_delete(request: web.Request) -> web.Response:
    """Hard-delete a task by id."""
    from sonya.tasks.store import TaskStore
    task_id = request.match_info.get("task_id", "").strip()
    if not task_id:
        return web.json_response({"error": "missing task_id"}, status=400)
    config = request.app["config"]
    sub = _get_substrate_writable(config)
    try:
        store = TaskStore(sub)
        deleted = store.delete(task_id)
        if not deleted:
            return web.json_response({"error": f"task {task_id} not found"}, status=404)
        return web.json_response({"ok": True, "task_id": task_id, "deleted": True})
    finally:
        sub.close()


async def api_task_detail(request: web.Request) -> web.Response:
    """Full task detail: model fields + completed_steps + session-handoff history.

    Handoff history is reconstructed from continuity_events (kinds:
    task.session_handoff, task.session_budget_exhausted, task.created,
    task.picked_up, task.step_done, task.failed, task.blocked, task.completed,
    task.unblocked) filtered by task_id in payload.
    """
    import json as _json
    from sonya.tasks.store import TaskStore
    task_id = request.match_info.get("task_id", "").strip()
    if not task_id:
        return web.json_response({"error": "missing task_id"}, status=400)
    config = request.app["config"]
    sub = _get_substrate(config)
    try:
        store = TaskStore(sub)
        try:
            t = store.get(task_id)
        except Exception:
            return web.json_response({"error": f"task {task_id} not found"}, status=404)

        # Pull all task-related continuity events for this task_id.
        # Filter via JSON LIKE (cheap and indexed-table-scan; tasks are
        # typically <1000 events each).
        cursor = sub.connection.execute(
            """
            SELECT seq, kind, payload_json, created_at
            FROM continuity_events
            WHERE kind LIKE 'task.%'
              AND payload_json LIKE ?
            ORDER BY seq ASC
            LIMIT 200
            """,
            (f'%"{task_id}"%',),
        )
        events: list[dict] = []
        for seq, kind, payload_json, created_at in cursor.fetchall():
            try:
                payload = _json.loads(payload_json) if payload_json else {}
            except Exception:
                payload = {}
            # Only keep events that actually reference this task_id (LIKE
            # could false-positive on substring match in summaries).
            if payload.get("task_id") != task_id:
                continue
            events.append({
                "seq": int(seq),
                "kind": kind,
                "payload": payload,
                "created_at": created_at,
            })

        return web.json_response({
            "task_id": t.task_id,
            "title": t.title,
            "description": t.description,
            "status": t.status.value,
            "created_by": t.created_by,
            "principal_id": t.principal_id,
            "scheduled_for": t.scheduled_for,
            "deadline": t.deadline,
            "notify_mode": t.notify_mode,
            "max_sessions": t.max_sessions,
            "sessions_used": t.sessions_used,
            "plan_steps": t.plan_steps,
            "completed_steps": t.completed_steps,  # [{step_idx, summary, completed_at}, ...]
            "blocker": t.blocker,
            "result": t.result,
            "last_session_notes": t.last_session_notes,
            "next_step_hint": t.next_step_hint,
            "created_at": t.created_at,
            "updated_at": t.updated_at,
            "events": events,
        })
    finally:
        sub.close()


async def _placeholder_kt(request: web.Request) -> web.Response:
    # Removed duplicate; real handler is api_providers_keys_test above.
    return web.json_response({"error": "not used"}, status=404)


# ============================================================
# OPERATOR PANEL — live cognitive state + intervention controls
# ============================================================
#
# Goal: give Ivan a single panel that shows what Sonya is doing right now
# (which window, which scheduler picks, recent agent_step events) and
# offers safe-but-direct controls (force active session, inject a
# message, repurpose / cancel a task). This complements Tasks panel
# (historical view) with a real-time operator view.
#
# All endpoints are read-only-ish or write a single substrate event —
# we never call into a running core process directly. Core process
# polls substrate and reacts, same way the existing trigger CLI does.


async def api_operator_snapshot(request: web.Request) -> web.Response:
    """Current cognitive state snapshot.

    Returns:
      - busy: whether something is running (last 60s scheduler events)
      - last_pick: most recent scheduler decision
      - active_session: currently-running session metadata if any
      - recent_picks: last 10 scheduler_pick events (audit)
      - open_tasks_summary: in_progress / blocked / pending counts
      - approved_proposals: count of pending APPROVED selfmod proposals
      - drives: current drive counter snapshot
      - last_external_trigger: most recent CLI/admin trigger event
    """
    import json
    config = request.app["config"]
    sub = _get_substrate(config)
    try:
        latest = ContinuityStream(sub).latest_seq()
        # Recent scheduler picks
        rows = sub.connection.execute(
            "SELECT seq, kind, created_at, payload_json FROM continuity_events "
            "WHERE kind = 'internal.scheduler_pick' ORDER BY seq DESC LIMIT 10"
        ).fetchall()
        recent_picks = []
        last_pick = None
        for r in rows:
            try:
                p = json.loads(r[3])
            except Exception:
                p = {}
            entry = {
                "seq": r[0],
                "at": r[2],
                "chosen_kind": p.get("chosen_kind"),
                "chosen_priority": p.get("chosen_priority"),
                "chosen_reason": p.get("chosen_reason"),
                "runners_up": p.get("runners_up", []),
            }
            recent_picks.append(entry)
            if last_pick is None:
                last_pick = entry
        # Currently-active session: agent_session_complete is the close
        # marker; if no complete after the last agent_step, we're inside
        # an active window.
        last_step = sub.connection.execute(
            "SELECT seq, kind, created_at, payload_json FROM continuity_events "
            "WHERE kind IN ('internal.agent_step', 'internal.agent_session_complete') "
            "ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        active_session = None
        if last_step is not None:
            kind = last_step[1]
            try:
                step_payload = json.loads(last_step[3])
            except Exception:
                step_payload = {}
            if kind == "internal.agent_step":
                # Find session start by walking back to step 0
                back = sub.connection.execute(
                    "SELECT seq, created_at, payload_json FROM continuity_events "
                    "WHERE kind = 'internal.agent_step' AND seq <= ? "
                    "ORDER BY seq DESC LIMIT 60",
                    (last_step[0],),
                ).fetchall()
                first_seq = last_step[0]
                first_at = last_step[2]
                for b in back:
                    try:
                        bp = json.loads(b[2])
                    except Exception:
                        continue
                    if str(bp.get("step", "")) == "0":
                        first_seq = b[0]
                        first_at = b[1]
                        break
                active_session = {
                    "first_step_seq": first_seq,
                    "started_at": first_at,
                    "current_step": step_payload.get("step"),
                    "current_tool": step_payload.get("tool"),
                    "last_step_at": last_step[2],
                }
        # Open tasks summary
        from sonya.tasks.store import TaskStore
        store = TaskStore(sub)
        open_tasks = store.list_open()
        recent_failed = store.list_recently_failed(hours=24, limit=10)
        summary = {
            "in_progress": sum(1 for t in open_tasks if t.status.value == "in_progress"),
            "blocked": sum(1 for t in open_tasks if t.status.value == "blocked"),
            "pending": sum(1 for t in open_tasks if t.status.value == "pending"),
            "recently_failed_24h": len(recent_failed),
        }
        # APPROVED selfmod proposals
        approved_count = 0
        try:
            from sonya.selfmod.proposal import ProposalStatus, ProposalStore
            approved_count = sum(
                1 for p in ProposalStore(sub).list_all()
                if p.status == ProposalStatus.APPROVED
            )
        except Exception:
            pass
        # Drives
        drives_snapshot = {}
        try:
            from sonya.initiative.drives import DriveCounters
            d = DriveCounters.load(sub)
            drives_snapshot = d.to_dict()
        except Exception:
            pass
        # Last external trigger
        ext_row = sub.connection.execute(
            "SELECT seq, created_at, payload_json FROM continuity_events "
            "WHERE kind = 'internal.active_session_requested_external' "
            "ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        last_external = None
        if ext_row is not None:
            try:
                ep = json.loads(ext_row[2])
            except Exception:
                ep = {}
            last_external = {
                "seq": ext_row[0],
                "at": ext_row[1],
                "reason": ep.get("reason", "(none)"),
            }
        return web.json_response({
            "latest_seq": latest,
            "active_session": active_session,
            "last_pick": last_pick,
            "recent_picks": recent_picks,
            "open_tasks_summary": summary,
            "approved_proposals_pending": approved_count,
            "drives": drives_snapshot,
            "last_external_trigger": last_external,
        })
    finally:
        sub.close()


async def api_operator_live_steps(request: web.Request) -> web.Response:
    """Stream of recent agent_step events for live operator view.

    Query params:
      since: int seq (return events strictly after this seq)
      limit: int max events to return (default 50, max 200)
    """
    import json
    config = request.app["config"]
    sub = _get_substrate(config)
    try:
        try:
            since = int(request.query.get("since", "0"))
        except ValueError:
            since = 0
        try:
            limit = max(1, min(200, int(request.query.get("limit", "50"))))
        except ValueError:
            limit = 50
        rows = sub.connection.execute(
            "SELECT seq, kind, created_at, payload_json FROM continuity_events "
            "WHERE seq > ? AND kind IN ("
            "  'internal.agent_step', 'internal.agent_session_complete', "
            "  'internal.agent_session_outcome', 'internal.scheduler_pick', "
            "  'internal.blocker_detected', 'internal.task_worker_outcome', "
            "  'internal.task_worker_tick', 'internal.cognitive_tick', "
            "  'incoming.telegram_message', 'outgoing.telegram_progress', "
            "  'outgoing.telegram_initiative', 'outgoing.telegram_response', "
            "  'self_mod.applied', 'self_mod.git_pushed', "
            "  'task.created', 'task.completed', 'task.failed', 'task.blocked', "
            "  'task.session_handoff'"
            ") ORDER BY seq ASC LIMIT ?",
            (since, limit),
        ).fetchall()
        events = []
        for r in rows:
            try:
                p = json.loads(r[3])
            except Exception:
                p = {}
            short = {}
            if r[1] == "internal.agent_step":
                short = {
                    "step": p.get("step"),
                    "type": p.get("type"),
                    "tool": p.get("tool"),
                    "arg": (str(p.get("arg") or "")[:200]),
                    "thought": (str(p.get("thought") or "")[:300]),
                    "content": (str(p.get("content") or "")[:300]),
                }
            elif r[1] == "internal.scheduler_pick":
                short = {
                    "chosen_kind": p.get("chosen_kind"),
                    "chosen_priority": p.get("chosen_priority"),
                    "chosen_reason": p.get("chosen_reason"),
                    "runners_count": len(p.get("runners_up", [])),
                }
            elif r[1] == "internal.blocker_detected":
                short = {
                    "step": p.get("step"),
                    "tool": p.get("tool"),
                    "blocker_kind": p.get("blocker_kind"),
                    "preview": p.get("preview", "")[:200],
                }
            elif r[1].startswith("outgoing."):
                short = {
                    "text": (p.get("text") or p.get("preview") or "")[:300],
                }
            elif r[1].startswith("incoming."):
                short = {
                    "text": (p.get("text") or "")[:300],
                    "channel": p.get("channel"),
                }
            elif r[1].startswith("task."):
                short = {
                    "task_id": p.get("task_id"),
                    "status": p.get("status"),
                    "next_step": (p.get("next_step") or "")[:200],
                }
            else:
                short = {k: v for k, v in p.items() if k not in (
                    "description", "result", "last_session_notes",
                    "thought", "content", "stdout", "stderr",
                )}
            events.append({
                "seq": r[0],
                "kind": r[1],
                "at": r[2],
                "data": short,
            })
        return web.json_response({"events": events, "since": since})
    finally:
        sub.close()


async def api_operator_trigger_active(request: web.Request) -> web.Response:
    """Append `internal.active_session_requested_external` so the running
    InternalProcess fires an active session within ~30s.

    Body (JSON, optional): {"reason": "free text label for audit"}
    """
    config = request.app["config"]
    try:
        data = await request.json()
    except Exception:
        data = {}
    reason = str(data.get("reason") or "operator_panel").strip()[:200]
    sub = _get_substrate_writable(config)
    try:
        from sonya.state.continuity_stream import ContinuityEvent
        ev = ContinuityStream(sub).append(ContinuityEvent(
            kind="internal.active_session_requested_external",
            payload={"reason": reason, "source": "admin/operator"},
        ))
        return web.json_response({
            "ok": True,
            "event_seq": ev.seq,
            "reason": reason,
            "note": "InternalProcess polls every ~30s; session should start within a tick.",
        })
    finally:
        sub.close()


async def api_operator_inject_message(request: web.Request) -> web.Response:
    """Append `incoming.telegram_message` as if Ivan typed it in TG.

    Useful for: pushing a clarification mid-task, scripted prompts,
    testing reply behavior without going through Telegram.

    Body: {"text": "...", "channel": "telegram" (optional)}
    """
    config = request.app["config"]
    try:
        data = await request.json()
    except Exception:
        data = {}
    text = str(data.get("text") or "").strip()
    if not text:
        return web.json_response(
            {"error": "text required"}, status=400,
        )
    channel = str(data.get("channel") or "telegram").strip().lower()
    primary_id = config.primary_user_tg_id or "5785127604"
    sub = _get_substrate_writable(config)
    try:
        from sonya.state.continuity_stream import ContinuityEvent
        ev = ContinuityStream(sub).append(ContinuityEvent(
            kind=f"incoming.{channel}_message",
            principal_id="ivan",
            payload={
                "channel": channel,
                "chat_id": primary_id,
                "sender_id": primary_id,
                "text": text,
                "media_kind": None,
                "is_private": True,
                "source": "admin/operator_inject",
            },
        ))
        return web.json_response({
            "ok": True,
            "event_seq": ev.seq,
            "text": text,
            "channel": channel,
            "note": (
                "Note: this is a SUBSTRATE-only inject. The TG handler "
                "doesn't poll substrate for new incoming events — it polls "
                "Telegram itself. So this is recorded in Sonya's continuity "
                "stream but won't trigger a TG reply session. To force a "
                "real reply, use the trigger-active endpoint instead and "
                "let the active session pick up the message via its "
                "context-builder visibility."
            ),
        })
    finally:
        sub.close()


async def api_operator_task_action(request: web.Request) -> web.Response:
    """Operator-side task lifecycle actions.

    Body: {"action": "fail|unblock|repurpose|delete", "reason": "..."}
    Path: /api/operator/task/{task_id}/action

    Actions:
      fail      — force-fail with operator reason (reflects to TG via
                  outbound for non-silent tasks)
      unblock   — clear blocker, set in_progress (alias for tasks.unblock)
      repurpose — failed/done → pending, fresh start; clears next_step_hint
      delete    — hard remove (alias for existing api_tasks_delete)
    """
    from sonya.tasks.store import TaskStore
    from sonya.tasks.service import TaskService
    from sonya.tasks.models import TaskStatus
    config = request.app["config"]
    task_id = request.match_info["task_id"]
    try:
        data = await request.json()
    except Exception:
        data = {}
    action = str(data.get("action") or "").strip().lower()
    reason = str(data.get("reason") or "operator action").strip()[:500]
    if action not in {"fail", "unblock", "repurpose", "delete"}:
        return web.json_response(
            {"error": f"unknown action: {action}"}, status=400,
        )
    sub = _get_substrate_writable(config)
    try:
        from sonya.tasks.models import TaskNotFoundError
        store = TaskStore(sub)
        try:
            task = store.get(task_id)
        except TaskNotFoundError:
            return web.json_response({"error": "task not found"}, status=404)
        svc = TaskService(store, stream=ContinuityStream(sub))
        if action == "fail":
            updated = svc.fail(task_id, reason=f"[operator] {reason}")
            return web.json_response({"ok": True, "task_id": task_id, "status": updated.status.value})
        if action == "unblock":
            # If not currently blocked, force flip via store directly so
            # operator can also revive an in_progress→stuck task.
            try:
                updated = svc.unblock(task_id)
            except Exception:
                updated = task
            if updated.status.value != "in_progress":
                from sonya.tasks.models import TaskStatus
                updated = store.update_status(task_id, TaskStatus.IN_PROGRESS)
                from sonya.state.continuity_stream import ContinuityEvent
                ContinuityStream(sub).append(ContinuityEvent(
                    kind="task.unblocked",
                    payload={"task_id": task_id, "operator_reason": reason},
                ))
            # If reason given, set as next_step_hint
            if reason:
                sub.connection.execute(
                    "UPDATE tasks SET next_step_hint = ?, updated_at = ? WHERE task_id = ?",
                    (reason, datetime.now(timezone.utc).isoformat(), task_id),
                )
                sub.connection.commit()
            return web.json_response({"ok": True, "task_id": task_id, "status": updated.status.value})
        if action == "repurpose":
            sub.connection.execute(
                "UPDATE tasks SET status='pending', blocker='', "
                "next_step_hint='', last_session_notes='', "
                "sessions_used=0, updated_at=? WHERE task_id=?",
                (datetime.now(timezone.utc).isoformat(), task_id),
            )
            sub.connection.commit()
            from sonya.state.continuity_stream import ContinuityEvent
            ContinuityStream(sub).append(ContinuityEvent(
                kind="task.repurposed",
                payload={
                    "task_id": task_id,
                    "operator_reason": reason,
                    "previous_status": task.status.value,
                },
            ))
            return web.json_response({"ok": True, "task_id": task_id, "status": "pending"})
        if action == "delete":
            sub.connection.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))
            sub.connection.commit()
            return web.json_response({"ok": True, "task_id": task_id, "deleted": True})
        return web.json_response({"error": "unreachable"}, status=500)
    finally:
        sub.close()


# ---------------------------------------------------------------------------
# Atrium endpoints (T0.7 — WS feed, T0.9 — nudge endpoint)
# ---------------------------------------------------------------------------
# `/atrium/feed` — WebSocket. Streams new continuity_events (channel-aware,
# excludes private). Atrium UI (Tauri app) подключается сюда для live-feed.
# Auth: header `X-Atrium-Token` = SONYA_ADMIN_PASSWORD.
# Query params: ?since_seq=N, ?channel=X, ?session_id=X.
# Meta-message every 60s with private_count_last_hour + current_focus + drives.
#
# `/api/atrium/nudge` — HTTP POST. Reply из reason-stream pane → inbox-drain
# активной session. Body: {session_id, text, ref_seq}.
#
# См. docs/atrium/CHANNELS.md §3 (WS) и §4 (nudge).
# ---------------------------------------------------------------------------


def _atrium_cors(response: web.Response) -> web.Response:
    """Add permissive CORS headers for Atrium endpoints.

    Atrium runs as Tauri app or local dev server (vite на :1420), оба
    отправляют Origin. Auth остаётся через X-Atrium-Token, поэтому
    разрешаем все origins безопасно — без правильного токена нельзя ничего.
    """
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Atrium-Token"
    return response


async def atrium_options(request: web.Request) -> web.Response:
    """CORS preflight for atrium endpoints."""
    return _atrium_cors(web.Response(status=204))


async def atrium_feed_ws(request: web.Request) -> web.WebSocketResponse:
    """WebSocket feed of new continuity events for Atrium UI.

    Auth: header `X-Atrium-Token` (preferred) ИЛИ query `?token=` (browser
    fallback — WebSocket spec не позволяет custom headers from JS).
    Filters private=1 events at SQL layer.
    """
    config = request.app["config"]
    admin_password = request.app.get("admin_password", "")
    # Auth — accept token from header или query (browser-friendly)
    token = request.headers.get("X-Atrium-Token", "") or request.query.get("token", "")
    if admin_password and token != admin_password:
        return web.json_response({"error": "auth"}, status=401)

    # Query params
    try:
        since_seq = int(request.query.get("since_seq", "0"))
    except ValueError:
        since_seq = 0
    channel_filter = request.query.get("channel") or None
    session_filter = request.query.get("session_id") or None

    ws = web.WebSocketResponse(heartbeat=30.0)
    await ws.prepare(request)

    sub = _get_substrate_writable(config)
    try:
        from sonya.state.continuity_stream import ContinuityStream as _CS

        stream = _CS(sub)
        # Initial catch-up: read everything since `since_seq`
        last_seq = since_seq
        for ev in stream.read_since_atrium(
            last_seq, channel=channel_filter, session_id=session_filter
        ):
            await ws.send_json(_atrium_event_to_json(ev))
            last_seq = ev.seq

        # Live loop: poll every second for new events + meta every 60s
        import asyncio as _asyncio
        meta_counter = 0
        while not ws.closed:
            try:
                # Wait for client messages with timeout (also drains pings/closes)
                try:
                    msg = await _asyncio.wait_for(ws.receive(), timeout=1.0)
                    if msg.type in (web.WSMsgType.CLOSE, web.WSMsgType.CLOSING, web.WSMsgType.CLOSED):
                        break
                except _asyncio.TimeoutError:
                    pass
                # Stream new events
                for ev in stream.read_since_atrium(
                    last_seq, channel=channel_filter, session_id=session_filter
                ):
                    await ws.send_json(_atrium_event_to_json(ev))
                    last_seq = ev.seq
                # Meta message every 60 ticks
                meta_counter += 1
                if meta_counter >= 60:
                    meta_counter = 0
                    try:
                        meta = _atrium_meta(sub, stream)
                        await ws.send_json(meta)
                    except Exception:
                        pass
            except ConnectionResetError:
                break
            except Exception:
                # Don't kill the connection on a single iteration error
                continue
    finally:
        sub.close()
    return ws


def _atrium_event_to_json(ev) -> dict:
    """Format a ContinuityEvent for /atrium/feed wire."""
    payload = ev.payload or {}
    src = ""
    if isinstance(payload, dict):
        src = payload.get("src") or _atrium_infer_src(ev.kind, payload)
    return {
        "type": "event",
        "seq": ev.seq,
        "ts": ev.created_at,
        "kind": ev.kind,
        "channel": ev.channel,
        "src": src,
        "session_id": payload.get("session_id") if isinstance(payload, dict) else None,
        "task_id": payload.get("task_id") if isinstance(payload, dict) else None,
        "principal_id": ev.principal_id,
        "text": payload.get("text", "") if isinstance(payload, dict) else "",
        "payload": payload,
    }


def _atrium_infer_src(kind: str, payload: dict) -> str:
    """Best-effort src classification when event doesn't have explicit src."""
    if kind.startswith("internal.thought"):
        return "idle"
    if kind.startswith("outgoing.worker_log") or kind.startswith("internal.task_worker"):
        return "worker"
    if kind.startswith("outgoing.dialog") or kind.startswith("outgoing.telegram") or kind.startswith("outgoing.response"):
        return "active"
    if kind.startswith("outgoing.mind") or kind.startswith("outgoing.body") or kind.startswith("outgoing.voice"):
        return "active"
    if kind.startswith("internal.scheduler") or kind.startswith("subject.lifecycle"):
        return "system"
    if kind.startswith("skill.") or "capability_gap" in kind:
        return "skill"
    return "system"


def _atrium_meta(sub, stream) -> dict:
    """Build periodic meta-message: private count + current focus + drives."""
    private_count = stream.private_count_recent(hours=1)
    try:
        row = sub.connection.execute(
            "SELECT current_focus, current_outfit, current_expression, mood_tint "
            "FROM subject_state WHERE id = 1"
        ).fetchone()
        current = {
            "current_focus": row[0] if row else "",
            "current_outfit": row[1] if row else "home",
            "current_expression": row[2] if row else "neutral",
            "mood_tint": row[3] if row else "neutral",
        }
    except Exception:
        current = {}
    try:
        ds_row = sub.connection.execute(
            "SELECT boredom_analog, curiosity_analog, relational_focus, pending_debt "
            "FROM drive_state WHERE id = 1"
        ).fetchone()
        drives = {
            "boredom": ds_row[0] if ds_row else 0.0,
            "curiosity": ds_row[1] if ds_row else 0.0,
            "relational_focus": ds_row[2] if ds_row else 0.0,
            "pending_debt": ds_row[3] if ds_row else 0.0,
        }
    except Exception:
        drives = {}
    from datetime import datetime, timezone
    return {
        "type": "meta",
        "ts": datetime.now(timezone.utc).isoformat(),
        "private_count_last_hour": private_count,
        "current": current,
        "drives": drives,
    }


async def atrium_nudge(request: web.Request) -> web.Response:
    """HTTP nudge endpoint — reply из reason-stream pane.

    Body: {session_id, text, ref_seq}
    Записывается как `internal.nudge_received` event. Текст также
    кладётся в substrate как `incoming.atrium_nudge` чтобы её активная
    session подхватила через context_builder. Если session уже завершилась
    — пишется `internal.nudge_missed`, response status=missed.
    См. docs/atrium/EVENT_SCHEMA.md §2.3.
    """
    config = request.app["config"]
    admin_password = request.app.get("admin_password", "")
    token = request.headers.get("X-Atrium-Token", "") or request.query.get("token", "")
    if admin_password and token != admin_password:
        return _atrium_cors(web.json_response({"error": "auth"}, status=401))
    try:
        data = await request.json()
    except Exception:
        data = {}
    session_id = str(data.get("session_id") or "").strip()
    text = str(data.get("text") or "").strip()
    ref_seq = data.get("ref_seq")
    try:
        ref_seq_int = int(ref_seq) if ref_seq is not None else None
    except (TypeError, ValueError):
        ref_seq_int = None
    if not text:
        return _atrium_cors(web.json_response({"error": "text required"}, status=400))

    sub = _get_substrate_writable(config)
    try:
        from sonya.state.continuity_stream import ContinuityStream, ContinuityEvent

        stream = ContinuityStream(sub)
        # Detect if a session is currently active. We can't easily tell from
        # substrate alone whether the agent loop is mid-step, but we record
        # both events: nudge_received (always) and incoming.atrium_nudge
        # (which the session's context_builder picks up via inbox-drain).
        stream.append(ContinuityEvent(
            kind="internal.nudge_received",
            principal_id="ivan",
            payload={
                "from": "atrium",
                "session_id": session_id,
                "ref_seq": ref_seq_int,
                "text": text,
            },
        ))
        # Also mirror as an incoming-style event so context_builder sees it
        # in its "recent inbox" lookup.
        stream.append(ContinuityEvent(
            kind="incoming.atrium_nudge",
            principal_id="ivan",
            payload={
                "session_id": session_id,
                "ref_seq": ref_seq_int,
                "text": text,
            },
        ))
        return _atrium_cors(web.json_response({
            "status": "queued",
            "session_id": session_id,
            "ref_seq": ref_seq_int,
        }))
    finally:
        sub.close()


def create_app() -> web.Application:
    config = load_config()
    import os
    admin_password = os.environ.get("SONYA_ADMIN_PASSWORD", "")
    app = web.Application(middlewares=[auth_middleware])
    app["config"] = config
    app["admin_password"] = admin_password
    app.router.add_get("/", handle_index)
    app.router.add_route("*", "/login", handle_login)
    app.router.add_get("/api/dashboard", api_dashboard)
    app.router.add_get("/api/thoughts", api_thoughts)
    app.router.add_get("/api/memory", api_memory)
    app.router.add_get("/api/telegram", api_telegram)
    app.router.add_post("/api/chat/send", api_chat_send)
    app.router.add_get("/api/audit", api_audit)
    app.router.add_get("/api/substrate", api_substrate)
    app.router.add_get("/api/core/status", api_core_status)
    app.router.add_post("/api/core/start", api_core_start)
    app.router.add_post("/api/core/stop", api_core_stop)
    app.router.add_get("/api/core/logs", api_core_logs)
    app.router.add_get("/api/selfmod/list", api_selfmod_list)
    app.router.add_get("/api/selfmod/{proposal_id}", api_selfmod_get)
    app.router.add_post("/api/selfmod/{proposal_id}/approve", api_selfmod_approve)
    app.router.add_post("/api/selfmod/{proposal_id}/deny", api_selfmod_deny)
    # Providers (key pool management)
    app.router.add_get("/api/providers", api_providers_get)
    app.router.add_post("/api/providers/settings", api_providers_settings)
    app.router.add_post("/api/providers/keys", api_providers_keys_add)
    app.router.add_post("/api/providers/keys/{key_id}", api_providers_keys_update)
    app.router.add_post("/api/providers/keys/{key_id}/delete", api_providers_keys_delete)
    app.router.add_post("/api/providers/keys/{key_id}/test", api_providers_keys_test)
    app.router.add_post("/api/providers/keys/{key_id}/status", api_providers_keys_status)
    app.router.add_post("/api/providers/balance/refresh", api_providers_balance_refresh)
    app.router.add_post("/api/providers/keys/{key_id}/balance/refresh", api_providers_balance_refresh)
    # LLM call audit + tasks (admin observability)
    app.router.add_get("/api/llm_calls", api_llm_calls)
    app.router.add_get("/api/tasks", api_tasks)
    app.router.add_get("/api/tasks/{task_id}", api_task_detail)
    app.router.add_delete("/api/tasks/{task_id}", api_tasks_delete)
    # Approvals (shell.run / pip.install / governed selfmod gates)
    app.router.add_get("/api/approvals", api_approvals_get)
    app.router.add_post("/api/approvals/{request_id}/{decision}", api_approvals_decide)
    # Operator panel (live cognitive view + intervention)
    app.router.add_get("/api/operator/snapshot", api_operator_snapshot)
    app.router.add_get("/api/operator/live", api_operator_live_steps)
    app.router.add_post("/api/operator/trigger-active", api_operator_trigger_active)
    app.router.add_post("/api/operator/inject-message", api_operator_inject_message)
    app.router.add_post("/api/operator/task/{task_id}/action", api_operator_task_action)
    # Atrium (multichannel UI/output package — Этап 0)
    app.router.add_get("/atrium/feed", atrium_feed_ws)
    app.router.add_post("/api/atrium/nudge", atrium_nudge)
    app.router.add_options("/api/atrium/nudge", atrium_options)
    return app


def main() -> None:
    app = create_app()
    print("Sonya Admin: http://0.0.0.0:8877")
    web.run_app(app, host="0.0.0.0", port=8877)
