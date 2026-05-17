"""Sonya Admin Panel — local web UI.

Run: python -m sonya.admin
Opens on http://localhost:8877
"""

from __future__ import annotations

import json
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
    sub = _get_substrate(config)
    try:
        stream = ContinuityStream(sub)
        latest = stream.latest_seq()
        start = max(0, latest - 50)
        events = list(stream.read_since(start))
        return web.json_response({
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
        recent = episodic.get_recent(limit=30)
        facts = semantic.get_all(limit=20)
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

        response = await plan_next(ctx, _Provider())
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
    """Primary anchor (Ivan) approves a REQUIRES_GOVERNED_CHANGE proposal."""
    config = request.app["config"]
    proposal_id = request.match_info.get("proposal_id", "")

    if _is_core_running(config):
        return web.json_response(
            {"error": "stop core first; admin cannot write while core runs"},
            status=409,
        )

    sub = _get_substrate(config)
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
            return web.json_response({
                "error": "no approval request found for this proposal — call selfmod.governed first",
            }, status=400)

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

    if _is_core_running(config):
        return web.json_response(
            {"error": "stop core first; admin cannot write while core runs"},
            status=409,
        )

    sub = _get_substrate(config)
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
    """Stop the core process: SIGTERM first, SIGKILL after 10s if still alive."""
    import signal
    import asyncio
    global _core_process, _core_log_file

    if _core_process is None or _core_process.returncode is not None:
        return web.json_response({"status": "not_running"})

    pid = _core_process.pid
    proc = _core_process

    # Graceful first
    try:
        proc.send_signal(signal.SIGTERM)
    except ProcessLookupError:
        _core_process = None
        return web.json_response({"status": "already_dead", "pid": pid})

    # Wait up to 10s for graceful exit
    for _ in range(20):
        await asyncio.sleep(0.5)
        if proc.poll() is not None:
            break

    method = "sigterm"
    if proc.poll() is None:
        # Still alive — escalate
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
    return app


def main() -> None:
    app = create_app()
    print("Sonya Admin: http://0.0.0.0:8877")
    web.run_app(app, host="0.0.0.0", port=8877)
