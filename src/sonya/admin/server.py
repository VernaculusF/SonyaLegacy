"""Sonya Admin Panel — local web UI.

Run: python -m sonya.admin
Opens on http://localhost:8877
"""

from __future__ import annotations

import json
import os
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
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
_ATRIUM_WS_TICKET_TTL_SECONDS = 45
_ATRIUM_DIST_DIR = Path(__file__).resolve().parents[3] / "packages" / "atrium" / "dist"


async def _json_body(request: web.Request) -> dict[str, Any]:
    try:
        data = await request.json()
    except json.JSONDecodeError as err:
        raise web.HTTPBadRequest(
            text=json.dumps({"error": "invalid_json", "detail": str(err)}, ensure_ascii=False),
            content_type="application/json",
        ) from err
    if not isinstance(data, dict):
        raise web.HTTPBadRequest(
            text=json.dumps({"error": "json_object_required"}, ensure_ascii=False),
            content_type="application/json",
        )
    return data


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
    # Atrium Console: the desktop app mirrors the admin panel and authenticates
    # with the X-Atrium-Token header (== admin_password), not the browser
    # cookie. Allow any /api/* call that presents a valid token so the Console
    # can reach operator/tasks/selfmod/providers/core/substrate endpoints
    # without the cookie/login flow. CORS preflight (OPTIONS) is always let
    # through so the browser can probe.
    if request.method == "OPTIONS":
        return await handler(request)
    if request.path.startswith("/api/"):
        token = request.headers.get("X-Atrium-Token", "") or request.query.get("token", "")
        if token == password:
            return await handler(request)
        if request.cookies.get("sonya_auth") == password:
            return await handler(request)
        return web.json_response({"error": "auth"}, status=401)
    # Check cookie
    if request.cookies.get("sonya_auth") == password:
        return await handler(request)
    # Check if this is login page
    if request.path == "/login":
        return await handler(request)
    # Redirect to login
    return web.HTTPFound("/login")


_SECURITY_CSP = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob: http: https:; "
    "media-src 'self' data: blob: http: https:; "
    "connect-src 'self' ws: wss: http: https:; "
    "font-src 'self' data:; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "frame-ancestors 'none'"
)


@middleware
async def security_headers_middleware(request: web.Request, handler):
    try:
        response = await handler(request)
    except web.HTTPException as exc:
        _apply_security_headers(exc.headers)
        raise
    _apply_security_headers(response.headers)
    return response


def _apply_security_headers(headers) -> None:
    headers.setdefault("Content-Security-Policy", _SECURITY_CSP)
    headers.setdefault("X-Content-Type-Options", "nosniff")
    headers.setdefault("Referrer-Policy", "no-referrer")
    headers.setdefault("X-Frame-Options", "DENY")
    headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")


def _issue_atrium_ws_ticket(app: web.Application) -> dict[str, Any]:
    ticket = secrets.token_urlsafe(32)
    expires_at = time.time() + _ATRIUM_WS_TICKET_TTL_SECONDS
    tickets = app["atrium_ws_tickets"]
    tickets[ticket] = expires_at
    _prune_atrium_ws_tickets(tickets)
    return {
        "ok": True,
        "ticket": ticket,
        "ttl_seconds": _ATRIUM_WS_TICKET_TTL_SECONDS,
        "expires_at": datetime.fromtimestamp(expires_at, tz=timezone.utc).isoformat(),
    }


def _prune_atrium_ws_tickets(tickets: dict[str, float]) -> None:
    now = time.time()
    expired = [ticket for ticket, expires_at in tickets.items() if expires_at <= now]
    for ticket in expired:
        tickets.pop(ticket, None)


def _consume_atrium_ws_ticket(app: web.Application, ticket: str) -> bool:
    if not ticket:
        return False
    tickets = app["atrium_ws_tickets"]
    _prune_atrium_ws_tickets(tickets)
    expires_at = tickets.pop(ticket, None)
    return bool(expires_at and expires_at > time.time())


@middleware
async def cors_middleware(request: web.Request, handler):
    """Add permissive CORS headers to all /api/ responses so the Atrium
    Console (served from a different origin in dev: localhost:1420) can call
    the admin endpoints with the X-Atrium-Token header. Handles OPTIONS
    preflight for any /api/ route up-front."""
    if request.path.startswith("/api/") and request.method == "OPTIONS":
        resp = web.Response(status=204)
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Atrium-Token"
        return resp
    try:
        resp = await handler(request)
    except web.HTTPException as exc:
        if request.path.startswith("/api/"):
            exc.headers["Access-Control-Allow-Origin"] = "*"
            exc.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Atrium-Token"
        raise
    if request.path.startswith("/api/"):
        resp.headers["Access-Control-Allow-Origin"] = "*"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Atrium-Token"
    return resp


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


async def handle_atrium_app(request: web.Request) -> web.Response:
    index = _ATRIUM_DIST_DIR / "index.html"
    if not index.is_file():
        return web.json_response(
            {"error": "atrium_bundle_missing", "detail": "build packages/atrium on the server"},
            status=503,
        )
    relative = str(request.match_info.get("path", "") or "").strip("/")
    candidate = (_ATRIUM_DIST_DIR / relative).resolve() if relative else index.resolve()
    try:
        candidate.relative_to(_ATRIUM_DIST_DIR.resolve())
    except ValueError:
        raise web.HTTPNotFound()
    if candidate.is_file():
        return web.FileResponse(candidate)
    first_segment = relative.split("/", 1)[0] if relative else ""
    if first_segment in {"assets", "avatar", "models"} or Path(relative).suffix:
        raise web.HTTPNotFound()
    return web.FileResponse(index)


async def handle_atrium_redirect(request: web.Request) -> web.Response:
    raise web.HTTPFound("/atrium/")


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
        from sonya.providers import KeyStore
        provider_settings = KeyStore(sub).get_settings()
        return web.json_response({
            "state": {
                "active_principal": state.active_principal_id,
                "emotional_vector": state.emotional_vector,
                "drift_signals": list(state.drift_signals),
                "pending_intentions": list(state.pending_intentions),
            },
            "latest_seq": latest_seq,
            "provider_settings": {
                "active_provider": provider_settings.active_provider,
                "default_model": provider_settings.default_model,
                "default_base_url": provider_settings.default_base_url,
                "updated_at": provider_settings.updated_at,
            },
            "config": {
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
    data = await _json_body(request)
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
        from sonya.providers import KeyStore, LLMProvider
        response = await plan_next(ctx, LLMProvider(KeyStore(sub)), purpose="admin_chat")
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


async def api_selfmod_archive(request: web.Request) -> web.Response:
    """Archive a terminal selfmod proposal so operator lists can be cleaned up."""
    config = request.app["config"]
    proposal_id = request.match_info.get("proposal_id", "")
    sub = _get_substrate_writable(config)
    try:
        from sonya.selfmod import ProposalStore
        from sonya.selfmod.proposal import ProposalNotFoundError, ProposalStatus

        store = ProposalStore(sub)
        try:
            p = store.get(proposal_id)
        except ProposalNotFoundError:
            return web.json_response({"error": "not found"}, status=404)

        terminal = {
            ProposalStatus.REJECTED,
            ProposalStatus.APPLIED,
            ProposalStatus.REVERTED,
            ProposalStatus.GOVERNED_APPROVED,
            ProposalStatus.APPROVED,
        }
        if p.status not in terminal:
            return web.json_response({"error": f"proposal status is {p.status.value}, archive only allowed for terminal proposals"}, status=400)
        store.update_status(proposal_id, ProposalStatus.ARCHIVED)
        return web.json_response({"status": "archived", "proposal_id": proposal_id})
    finally:
        sub.close()


async def api_selfmod_clear_archived(request: web.Request) -> web.Response:
    """Delete archived proposals from substrate for operator hygiene."""
    config = request.app["config"]
    sub = _get_substrate_writable(config)
    try:
        cur = sub.connection.execute("SELECT COUNT(*) FROM self_mod_proposals WHERE status = 'archived'")
        row = cur.fetchone()
        count = int(row[0]) if row else 0
        sub.connection.execute("DELETE FROM self_mod_proposals WHERE status = 'archived'")
        sub.connection.commit()
        return web.json_response({"status": "cleared", "removed": count})
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


def _json_arg(value: Any) -> str:
    if isinstance(value, str):
        return value or "{}"
    return json.dumps(value if value is not None else {}, ensure_ascii=False)


def _provider_payload(provider) -> dict[str, Any]:
    return {
        "provider_id": provider.provider_id,
        "display_name": provider.display_name,
        "adapter_kind": provider.adapter_kind,
        "status": provider.status,
        "base_url": provider.base_url,
        "capabilities": json.loads(provider.capabilities_json or "{}"),
        "constraints": json.loads(provider.constraints_json or "{}"),
        "metadata": json.loads(provider.metadata_json or "{}"),
        "created_at": provider.created_at,
        "updated_at": provider.updated_at,
    }


def _account_payload(account) -> dict[str, Any]:
    return {
        "account_id": account.account_id,
        "provider_id": account.provider_id,
        "name": account.name,
        "secret_ref": account.secret_ref,
        "secret_masked": account.masked_secret,
        "legacy_key_id": account.legacy_key_id,
        "status": account.status,
        "priority": account.priority,
        "constraints": json.loads(account.constraints_json or "{}"),
        "metadata": json.loads(account.metadata_json or "{}"),
        "created_at": account.created_at,
        "updated_at": account.updated_at,
    }


def _model_payload(model) -> dict[str, Any]:
    return {
        "model_id": model.model_id,
        "provider": model.provider,
        "provider_model_key": f"{model.provider}::{model.model_id}",
        "model_name": model.model_name,
        "context_length": model.context_length,
        "modalities": model.modalities(),
        "cost_per_1m_input_tokens": model.cost_per_1m_input_tokens,
        "cost_per_1m_output_tokens": model.cost_per_1m_output_tokens,
        "is_free": bool(model.is_free),
        "latency_tier": model.latency_tier,
        "strengths": model.strengths(),
        "role_preference": model.role_preference,
        "enabled": bool(model.enabled),
        "text_loop_ok": bool(model.text_loop_ok),
        "last_checked_at": model.last_checked_at,
        "discovery_source": model.discovery_source,
        "metadata": model.metadata(),
        "created_at": model.created_at,
        "updated_at": model.updated_at,
    }


def _quota_payload(quota) -> dict[str, Any]:
    return {
        "quota_window_id": quota.quota_window_id,
        "account_id": quota.account_id,
        "quota_kind": quota.quota_kind,
        "limit_value": quota.limit_value,
        "used_value": quota.used_value,
        "remaining_value": quota.remaining_value,
        "unit": quota.unit,
        "window_started_at": quota.window_started_at,
        "resets_at": quota.resets_at,
        "observed_at": quota.observed_at,
        "metadata": json.loads(quota.metadata_json or "{}"),
    }


def _observation_payload(observation) -> dict[str, Any]:
    return {
        "observation_id": observation.observation_id,
        "provider_id": observation.provider_id,
        "account_id": observation.account_id,
        "model_id": observation.model_id,
        "observation_kind": observation.observation_kind,
        "success": bool(observation.success),
        "latency_ms": observation.latency_ms,
        "value": json.loads(observation.value_json or "{}"),
        "observed_at": observation.observed_at,
    }


async def api_providers_get(request: web.Request) -> web.Response:
    """List provider settings + all keys (masked)."""
    from sonya.providers import KeyStore
    config = request.app["config"]
    sub = _get_substrate(config)
    try:
        store = KeyStore(sub)
        settings = store.get_settings()
        keys = store.list_keys()
        accounts = store.list_provider_accounts()
        return web.json_response({
            "settings": {
                "active_provider": settings.active_provider,
                "default_model": settings.default_model,
                "default_base_url": settings.default_base_url,
                "updated_at": settings.updated_at,
            },
            "providers": [_provider_payload(p) for p in store.list_providers()],
            "accounts": [_account_payload(a) for a in accounts],
            "models": [_model_payload(m) for m in store.list_provider_models(enabled_only=False)],
            "available_models": [_model_payload(m) for m in store.list_available_provider_models()],
            "account_offerings": [
                {
                    **offering,
                    "provider_model_key": (
                        f"{offering['provider_id']}::{offering['model_id']}"
                    ),
                }
                for offering in store.list_account_offerings()
            ],
            "quota_windows": [
                _quota_payload(q)
                for account in accounts
                for q in store.list_quota_windows(account.account_id)
            ],
            "observations": [
                _observation_payload(o)
                for provider in store.list_providers()
                for o in store.list_provider_observations(provider_id=provider.provider_id)[:10]
            ],
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


async def api_providers_registry_upsert(request: web.Request) -> web.Response:
    from sonya.providers import KeyStore
    config = request.app["config"]
    data = await _json_body(request)
    provider_id = str(data.get("provider_id") or data.get("provider") or "").strip().lower()
    if not provider_id:
        return web.json_response({"error": "missing required field: provider_id"}, status=400)
    sub = _get_substrate_writable(config)
    try:
        store = KeyStore(sub)
        provider = store.upsert_provider(
            provider_id=provider_id,
            display_name=str(data.get("display_name") or provider_id).strip(),
            adapter_kind=str(data.get("adapter_kind") or "openai_compatible").strip(),
            status=str(data.get("status") or "active").strip().lower(),
            base_url=str(data.get("base_url") or "").strip(),
            capabilities_json=_json_arg(data.get("capabilities_json", data.get("capabilities", {}))),
            constraints_json=_json_arg(data.get("constraints_json", data.get("constraints", {}))),
            metadata_json=_json_arg(data.get("metadata_json", data.get("metadata", {}))),
        )
        return web.json_response({"status": "upserted", "provider": _provider_payload(provider)})
    finally:
        sub.close()


async def api_providers_registry_delete(request: web.Request) -> web.Response:
    from sonya.providers import KeyStore
    config = request.app["config"]
    provider_id = request.match_info["provider_id"].strip().lower()
    sub = _get_substrate_writable(config)
    try:
        store = KeyStore(sub)
        if store.get_provider(provider_id) is None:
            return web.json_response({"error": "not found"}, status=404)
        accounts = store.list_provider_accounts(provider_id)
        if accounts:
            return web.json_response({"error": "accounts still exist", "accounts": len(accounts)}, status=409)
        store.delete_provider(provider_id)
        return web.json_response({"status": "deleted", "provider_id": provider_id})
    finally:
        sub.close()


async def api_providers_registry_refresh(request: web.Request) -> web.Response:
    from sonya.providers import KeyStore
    from sonya.providers.adapters import factory as adapter_factory
    from sonya.providers.refresh import ProviderRefreshService

    config = request.app["config"]
    provider_id = request.match_info["provider_id"].strip().lower()
    sub = _get_substrate_writable(config)
    try:
        store = KeyStore(sub)
        if store.get_provider(provider_id) is None:
            return web.json_response({"error": "not found"}, status=404)
        try:
            accounts = [
                account for account in store.list_provider_accounts(provider_id)
                if account.status == "active"
            ]
            if not accounts:
                return web.json_response({"error": "no active accounts"}, status=409)
            adapters = {
                account.account_id: adapter_factory.build_lifecycle_adapter_for_account(
                    store,
                    provider_id,
                    account.account_id,
                )
                for account in accounts
            }
            result = await ProviderRefreshService(
                store,
                adapters,
            ).refresh_provider(provider_id)
        except (KeyError, RuntimeError, ValueError) as exc:
            return web.json_response({"error": str(exc)}, status=409)
        return web.json_response({
            "provider_id": result.provider_id,
            "ok": result.ok,
            "models_seen": result.models_seen,
            "quotas_seen": result.quotas_seen,
            "error": result.error,
        })
    finally:
        sub.close()


async def api_providers_accounts_add(request: web.Request) -> web.Response:
    from sonya.providers import KeyStore
    config = request.app["config"]
    data = await _json_body(request)
    provider_id = str(data.get("provider_id") or data.get("provider") or "").strip().lower()
    name = str(data.get("name") or "").strip()
    if not provider_id or not name:
        return web.json_response({"error": "provider_id and name are required"}, status=400)
    if data.get("secret_value") or data.get("api_key"):
        return web.json_response({
            "error": "raw credentials require the protected secret-ingestion endpoint",
        }, status=400)
    sub = _get_substrate_writable(config)
    try:
        store = KeyStore(sub)
        account = store.add_provider_account(
            provider_id=provider_id,
            name=name,
            secret_ref=str(data.get("secret_ref") or "").strip(),
            status=str(data.get("status") or "active").strip().lower(),
            priority=int(data.get("priority") or 0),
            constraints_json=_json_arg(data.get("constraints_json", data.get("constraints", {}))),
            metadata_json=_json_arg(data.get("metadata_json", data.get("metadata", {}))),
        )
        return web.json_response({"status": "added", "account": _account_payload(account)})
    finally:
        sub.close()


async def api_providers_account_secret_ingest(request: web.Request) -> web.Response:
    """Rotate an account secret from an opaque authenticated request body.

    Raw secret material is never parsed as JSON, returned, audited, or written
    to continuity/tool traces.
    """
    from sonya.providers import KeyStore

    if not request.app.get("admin_password"):
        return web.json_response(
            {"error": "protected secret-ingestion requires SONYA_ADMIN_PASSWORD"},
            status=503,
        )
    if request.content_type != "application/octet-stream":
        return web.json_response(
            {"error": "content-type must be application/octet-stream"},
            status=415,
        )
    body = await request.read()
    if not body:
        return web.json_response({"error": "secret body is required"}, status=400)
    if len(body) > 64 * 1024:
        return web.json_response({"error": "secret body is too large"}, status=413)
    try:
        raw_secret = body.decode("utf-8").strip()
    except UnicodeDecodeError:
        return web.json_response({"error": "secret body must be UTF-8"}, status=400)
    if not raw_secret:
        return web.json_response({"error": "secret body is required"}, status=400)

    config = request.app["config"]
    account_id = request.match_info["account_id"]
    sub = _get_substrate_writable(config)
    try:
        store = KeyStore(sub)
        if store.get_provider_account(account_id) is None:
            return web.json_response({"error": "not found"}, status=404)
        account = store.rotate_account_secret(account_id, raw_secret)
        AuditLog(sub).append(
            principal_id="ivan",
            action="provider_secret_ingest",
            decision="allow",
            scope=f"provider_account:{account_id}",
            metadata={
                "provider_id": account.provider_id,
                "account_id": account.account_id,
                "secret_ref": account.secret_ref,
                "secret_masked": account.masked_secret,
            },
        )
        return web.json_response({"status": "rotated", "account": _account_payload(account)})
    finally:
        raw_secret = ""
        sub.close()


async def api_providers_accounts_update(request: web.Request) -> web.Response:
    from sonya.providers import KeyStore
    config = request.app["config"]
    account_id = request.match_info["account_id"]
    data = await _json_body(request)
    sub = _get_substrate_writable(config)
    try:
        store = KeyStore(sub)
        if store.get_provider_account(account_id) is None:
            return web.json_response({"error": "not found"}, status=404)
        account = store.update_provider_account(
            account_id,
            name=str(data["name"]).strip() if "name" in data else None,
            status=str(data["status"]).strip().lower() if "status" in data else None,
            priority=int(data["priority"]) if "priority" in data else None,
            constraints_json=_json_arg(data["constraints"]) if "constraints" in data else data.get("constraints_json"),
            metadata_json=_json_arg(data["metadata"]) if "metadata" in data else data.get("metadata_json"),
        )
        return web.json_response({"status": "updated", "account": _account_payload(account)})
    finally:
        sub.close()


async def api_providers_accounts_delete(request: web.Request) -> web.Response:
    from sonya.providers import KeyStore
    config = request.app["config"]
    account_id = request.match_info["account_id"]
    sub = _get_substrate_writable(config)
    try:
        store = KeyStore(sub)
        if store.get_provider_account(account_id) is None:
            return web.json_response({"error": "not found"}, status=404)
        store.delete_provider_account(account_id)
        return web.json_response({"status": "deleted", "account_id": account_id})
    finally:
        sub.close()


async def api_providers_account_offering_set(request: web.Request) -> web.Response:
    from sonya.providers import KeyStore
    config = request.app["config"]
    data = await _json_body(request)
    account_id = str(data.get("account_id") or "").strip()
    model_id = str(data.get("model_id") or data.get("model") or "").strip()
    if not account_id or not model_id:
        return web.json_response({"error": "account_id and model_id are required"}, status=400)
    sub = _get_substrate_writable(config)
    try:
        store = KeyStore(sub)
        store.set_account_offering(
            account_id,
            model_id,
            enabled=bool(data.get("enabled", True)),
            metadata_json=_json_arg(data.get("metadata_json", data.get("metadata", {}))),
        )
        return web.json_response({
            "status": "updated",
            "account_id": account_id,
            "model_id": model_id,
            "enabled": bool(data.get("enabled", True)),
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
    data = await _json_body(request)
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
    """Reject the legacy plaintext-key JSON endpoint."""
    return web.json_response({
        "error": (
            "legacy plaintext key ingestion is disabled; create a provider account "
            "and use the protected secret-ingestion endpoint"
        ),
    }, status=400)


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
    data = await _json_body(request)
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
    data = await _json_body(request)
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
    from sonya.work.store import WorkItemStore
    config = request.app["config"]
    sub = _get_substrate(config)
    try:
        store = WorkItemStore(sub)
        tasks = store.list_all(limit=100)
        return web.json_response({
            "tasks": [
                {
                    "item_id": t.item_id,
                    "title": t.title,
                    "description": t.description,
                    "status": t.status.value,
                    "created_by": t.origin,
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
    from sonya.work.store import WorkItemStore
    item_id = request.match_info.get("item_id", "").strip()
    if not item_id:
        return web.json_response({"error": "missing item_id"}, status=400)
    config = request.app["config"]
    sub = _get_substrate_writable(config)
    try:
        store = WorkItemStore(sub)
        deleted = store.delete(item_id)
        if not deleted:
            return web.json_response({"error": f"task {item_id} not found"}, status=404)
        return web.json_response({"ok": True, "item_id": item_id, "deleted": True})
    finally:
        sub.close()


async def api_task_detail(request: web.Request) -> web.Response:
    """Full task detail: model fields + completed_steps + session-handoff history.

    Handoff history is reconstructed from continuity_events (kinds:
    task.session_handoff, task.session_budget_exhausted, task.created,
    task.picked_up, task.step_done, task.failed, task.blocked, task.completed,
    task.unblocked) filtered by item_id in payload.
    """
    import json as _json
    from sonya.work.store import WorkItemStore
    item_id = request.match_info.get("item_id", "").strip()
    if not item_id:
        return web.json_response({"error": "missing item_id"}, status=400)
    config = request.app["config"]
    sub = _get_substrate(config)
    try:
        store = WorkItemStore(sub)
        try:
            t = store.get(item_id)
        except Exception:
            return web.json_response({"error": f"task {item_id} not found"}, status=404)

        # Pull all task-related continuity events for this item_id.
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
            (f'%"{item_id}"%',),
        )
        events: list[dict] = []
        for seq, kind, payload_json, created_at in cursor.fetchall():
            try:
                payload = _json.loads(payload_json) if payload_json else {}
            except Exception:
                payload = {}
            # Only keep events that actually reference this item_id (LIKE
            # could false-positive on substring match in summaries).
            if payload.get("item_id") != item_id:
                continue
            events.append({
                "seq": int(seq),
                "kind": kind,
                "payload": payload,
                "created_at": created_at,
            })

        return web.json_response({
            "item_id": t.item_id,
            "title": t.title,
            "description": t.description,
            "status": t.status.value,
            "created_by": t.origin,
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
        from sonya.work.store import WorkItemStore
        store = WorkItemStore(sub)
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
                    "item_id": p.get("item_id"),
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
        data = await _json_body(request)
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
        data = await _json_body(request)
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
    Path: /api/operator/task/{item_id}/action

    Actions:
      fail      — force-fail with operator reason (reflects to TG via
                  outbound for non-silent tasks)
      unblock   — clear blocker, set in_progress (alias for tasks.unblock)
      repurpose — failed/done → pending, fresh start; clears next_step_hint
      delete    — hard remove (alias for existing api_tasks_delete)
    """
    from sonya.work.store import WorkItemStore
    from sonya.work.service import WorkItemService
    from sonya.work.models import WorkItemStatus
    config = request.app["config"]
    item_id = request.match_info["item_id"]
    try:
        data = await _json_body(request)
    except Exception:
        data = {}
    action = str(data.get("action") or "").strip().lower()
    reason = str(data.get("reason") or "operator action").strip()[:500]
    if action not in {"fail", "unblock", "repurpose", "delete", "pause", "resume"}:
        return web.json_response(
            {"error": f"unknown action: {action}"}, status=400,
        )
    sub = _get_substrate_writable(config)
    try:
        from sonya.work.models import WorkItemNotFoundError
        store = WorkItemStore(sub)
        try:
            task = store.get(item_id)
        except WorkItemNotFoundError:
            return web.json_response({"error": "task not found"}, status=404)
        svc = WorkItemService(store, stream=ContinuityStream(sub))
        if action == "pause":
            if task.status in (WorkItemStatus.DONE, WorkItemStatus.FAILED):
                return web.json_response(
                    {"error": f"cannot pause a {task.status.value} task"}, status=409)
            store.update_status(item_id, WorkItemStatus.PAUSED)
            from sonya.state.continuity_stream import ContinuityEvent
            ContinuityStream(sub).append(ContinuityEvent(
                kind="task.paused",
                payload={"item_id": item_id, "operator_reason": reason},
            ))
            return web.json_response({"ok": True, "item_id": item_id, "status": "paused"})
        if action == "resume":
            if task.status != WorkItemStatus.PAUSED:
                return web.json_response(
                    {"error": f"task is {task.status.value}, not paused"}, status=409)
            store.update_status(item_id, WorkItemStatus.IN_PROGRESS)
            from sonya.state.continuity_stream import ContinuityEvent
            ContinuityStream(sub).append(ContinuityEvent(
                kind="task.resumed",
                payload={"item_id": item_id, "operator_reason": reason},
            ))
            return web.json_response({"ok": True, "item_id": item_id, "status": "in_progress"})
        if action == "fail":
            updated = svc.fail(item_id, reason=f"[operator] {reason}")
            return web.json_response({"ok": True, "item_id": item_id, "status": updated.status.value})
        if action == "unblock":
            # If not currently blocked, force flip via store directly so
            # operator can also revive an in_progress→stuck task.
            try:
                updated = svc.unblock(item_id)
            except Exception:
                updated = task
            if updated.status.value != "in_progress":
                from sonya.work.models import WorkItemStatus
                updated = store.update_status(item_id, WorkItemStatus.IN_PROGRESS)
                from sonya.state.continuity_stream import ContinuityEvent
                ContinuityStream(sub).append(ContinuityEvent(
                    kind="task.unblocked",
                    payload={"item_id": item_id, "operator_reason": reason},
                ))
            # If reason given, set as next_step_hint
            if reason:
                sub.connection.execute(
                    "UPDATE tasks SET next_step_hint = ?, updated_at = ? WHERE item_id = ?",
                    (reason, datetime.now(timezone.utc).isoformat(), item_id),
                )
                sub.connection.commit()
            return web.json_response({"ok": True, "item_id": item_id, "status": updated.status.value})
        if action == "repurpose":
            sub.connection.execute(
                "UPDATE tasks SET status='pending', blocker='', "
                "next_step_hint='', last_session_notes='', "
                "sessions_used=0, updated_at=? WHERE item_id=?",
                (datetime.now(timezone.utc).isoformat(), item_id),
            )
            sub.connection.commit()
            from sonya.state.continuity_stream import ContinuityEvent
            ContinuityStream(sub).append(ContinuityEvent(
                kind="task.repurposed",
                payload={
                    "item_id": item_id,
                    "operator_reason": reason,
                    "previous_status": task.status.value,
                },
            ))
            return web.json_response({"ok": True, "item_id": item_id, "status": "pending"})
        if action == "delete":
            sub.connection.execute("DELETE FROM tasks WHERE item_id = ?", (item_id,))
            sub.connection.commit()
            return web.json_response({"ok": True, "item_id": item_id, "deleted": True})
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


async def atrium_ws_ticket(request: web.Request) -> web.Response:
    """Issue a short-lived one-time ticket for a browser WebSocket upgrade."""
    admin_password = request.app.get("admin_password", "")
    token = request.headers.get("X-Atrium-Token", "")
    if admin_password and token != admin_password:
        return _atrium_cors(web.json_response({"error": "auth"}, status=401))
    return _atrium_cors(web.json_response(_issue_atrium_ws_ticket(request.app)))


def _atrium_catchup_since(since_seq: int, latest: int, backlog: int) -> int:
    """Compute the effective starting seq for /atrium/feed catch-up.

    A cold-start client (since_seq<=0) must NOT replay the entire history —
    that floods the UI and can trigger a reconnect→replay loop. Clamp the
    backlog to a recent tail. A resuming client (since_seq>0) keeps its seq.
    """
    if since_seq > 0:
        return since_seq
    if backlog <= 0:
        return 0
    return max(0, latest - backlog)


async def atrium_feed_ws(request: web.Request) -> web.WebSocketResponse:
    """WebSocket feed of new continuity events for Atrium UI.

    Auth: header `X-Atrium-Token` for non-browser clients or a short-lived,
    one-time query `?ticket=` issued by `/api/atrium/ws-ticket`.
    Filters private=1 events at SQL layer.
    """
    config = request.app["config"]
    admin_password = request.app.get("admin_password", "")
    token = request.headers.get("X-Atrium-Token", "")
    ticket = request.query.get("ticket", "")
    if admin_password and token != admin_password and not _consume_atrium_ws_ticket(request.app, ticket):
        return web.json_response({"error": "auth"}, status=401)

    # Query params
    try:
        since_seq = int(request.query.get("since_seq", "0"))
    except ValueError:
        since_seq = 0
    channel_filter = request.query.get("channel") or None
    session_filter = request.query.get("session_id") or None
    # Catch-up clamp: a cold-start client (since_seq=0) must NOT get the full
    # 10k+ event history replayed — that floods the UI, freezes it on O(n)
    # re-renders, and can drop the socket → reconnect → replay loop. Clamp the
    # backlog to a recent tail. Live events after connect always flow in full.
    try:
        backlog = int(request.query.get("backlog", "200"))
    except ValueError:
        backlog = 200
    backlog = max(0, min(backlog, 2000))

    ws = web.WebSocketResponse(heartbeat=30.0)
    await ws.prepare(request)

    sub = _get_substrate_writable(config)
    try:
        from sonya.state.continuity_stream import ContinuityStream as _CS

        stream = _CS(sub)
        # T1.5: mark Atrium connected so OutboundGate knows the primary
        # dialog channel is live (affects TG emergency-fallback decision).
        _atrium_mark_seen(sub)
        # Initial catch-up: read since `since_seq`, but clamp the backlog so a
        # cold-start client (since_seq=0) doesn't get the entire history
        # replayed. We only need the recent tail to populate the UI; older
        # events are reachable via the admin panel, not the live feed.
        latest = stream.latest_seq()
        effective_since = _atrium_catchup_since(since_seq, latest, backlog)
        last_seq = effective_since
        for ev in stream.read_since_atrium(
            last_seq, channel=channel_filter, session_id=session_filter
        ):
            await ws.send_json(_atrium_event_to_json(ev))
            last_seq = ev.seq
        # Sentinel: tells the client the backlog is done and live events
        # follow. The client uses this to suppress notifications / avatar
        # glow / chat scroll-jank during the initial sync.
        try:
            await ws.send_json({"type": "synced", "last_seq": last_seq})
        except Exception:
            pass

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
                # Meta message every 60 ticks; also refresh the connection
                # heartbeat so OutboundGate sees Atrium as live.
                meta_counter += 1
                if meta_counter >= 60:
                    meta_counter = 0
                    _atrium_mark_seen(sub)
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
        "item_id": payload.get("item_id") if isinstance(payload, dict) else None,
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
        from sonya.state.embodiment import EmbodimentStore
        emb = EmbodimentStore(sub).load()
        current = {
            "current_focus": emb.focus,
            "current_outfit": emb.outfit,
            "current_expression": emb.expression,
            "mood_tint": emb.mood_tint,
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
        data = await _json_body(request)
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


async def atrium_dialog(request: web.Request) -> web.Response:
    """HTTP dialog endpoint (T1.4) — Ivan types in the Atrium composer.

    Unlike `/api/atrium/nudge` (which targets a *running* session), this is a
    fresh turn from Ivan addressed to Sonya whether she's idle or busy. It:

      1. Records `incoming.atrium_dialog` (principal=ivan) — context_builder
         surfaces it as "[Иван написал]" so the next session replies to it.
      2. Appends `internal.active_session_requested_external` so the core's
         InternalProcess fires an active session within ~30s. That session
         reads the message via its context-builder and answers via chat.dialog.

    Admin and core are separate processes sharing only the substrate, so this
    substrate-event + trigger combo is the cross-process path (same mechanism
    the operator inject + trigger-active endpoints already use).

    Body: {"text": "..."}
    """
    config = request.app["config"]
    admin_password = request.app.get("admin_password", "")
    token = request.headers.get("X-Atrium-Token", "") or request.query.get("token", "")
    if admin_password and token != admin_password:
        return _atrium_cors(web.json_response({"error": "auth"}, status=401))
    try:
        data = await _json_body(request)
    except Exception:
        data = {}
    text = str(data.get("text") or "").strip()
    workspace_id = str(data.get("workspace_id") or "").strip()
    # Optional attachment metadata (uploaded separately via /api/atrium/upload,
    # which returns {name, media_path, media_mime, media_kind}). The composer
    # passes these back here so the incoming event carries the reference.
    attachments = data.get("attachments")
    if not isinstance(attachments, list):
        attachments = []
    for attachment in attachments:
        if not isinstance(attachment, dict):
            return _atrium_cors(web.json_response(
                {"error": "invalid attachment metadata"}, status=400))
        attachment_workspace_id = str(attachment.get("workspace_id") or "").strip()
        if attachment_workspace_id != workspace_id:
            return _atrium_cors(web.json_response(
                {"error": "attachment workspace does not match dialog workspace"},
                status=400))
    if not text and not attachments:
        return _atrium_cors(web.json_response({"error": "text or attachment required"}, status=400))

    sub = _get_substrate_writable(config)
    try:
        from sonya.state.continuity_stream import ContinuityStream, ContinuityEvent

        if workspace_id and workspace_id != "main":
            from sonya.project import ProjectStore
            from sonya.project.model import ProjectNotFoundError
            project_store = ProjectStore(sub)
            try:
                project = project_store.get(workspace_id)
            except ProjectNotFoundError:
                return _atrium_cors(web.json_response(
                    {"error": "workspace not found"}, status=404))
            if project.status == "waiting_choice":
                project_store.set_status(
                    workspace_id,
                    "in_progress",
                    reason="Ivan replied in project chat",
                    source="atrium_dialog",
                )
            elif project.status != "in_progress":
                return _atrium_cors(web.json_response({
                    "error": f"project is read-only while status is '{project.status}'",
                    "project_id": workspace_id,
                    "status": project.status,
                }, status=409))

        stream = ContinuityStream(sub)
        primary_id = config.primary_user_tg_id or "5785127604"
        # First attachment (if any) is wired into media_path/media_mime so the
        # active session's vision path (channel_session._build_initial_user_message)
        # can attach it for image/video-capable models.
        first = attachments[0] if attachments else {}
        payload = {
            "channel": "dialog",
            "chat_id": primary_id,
            "sender_id": primary_id,
            "text": text,
            "source": "atrium/composer",
            "is_private": True,
        }
        if first:
            payload["media_path"] = first.get("media_path")
            payload["media_mime"] = first.get("media_mime")
            payload["media_kind"] = first.get("media_kind")
        if attachments:
            payload["attachments"] = attachments
        if workspace_id:
            payload["workspace_id"] = workspace_id
        ev = stream.append(ContinuityEvent(
            kind="incoming.atrium_dialog",
            channel="dialog",
            principal_id="ivan",
            payload=payload,
        ))
        try:
            from sonya.state.situational import record_ivan_activity

            record_ivan_activity(
                sub,
                source="incoming.atrium_dialog",
                source_ref=str(ev.seq or ""),
                stream=stream,
            )
        except Exception:
            pass
        # Wake the core: request an active session so she replies promptly.
        stream.append(ContinuityEvent(
            kind="internal.active_session_requested_external",
            payload={"reason": "atrium_dialog", "source": "atrium/composer"},
        ))
        return _atrium_cors(web.json_response({
            "status": "queued",
            "event_seq": ev.seq,
            "text": text,
            "attachments": len(attachments),
            "note": "active session triggered; reply within ~30s",
        }))
    finally:
        sub.close()


async def atrium_history(request: web.Request) -> web.Response:
    """Paginated dialog history for the Atrium scroll-up loader.

    Query: before_seq=N (load messages strictly before this seq), limit=50 (max 100).
    Returns oldest→newest tuples so the client can prepend in order.
    Body shape mirrors what /atrium/feed sends for dialog kinds.
    """
    config = request.app["config"]
    admin_password = request.app.get("admin_password", "")
    token = request.headers.get("X-Atrium-Token", "") or request.query.get("token", "")
    if admin_password and token != admin_password:
        return _atrium_cors(web.json_response({"error": "auth"}, status=401))
    try:
        before_seq = int(request.query.get("before_seq", "0"))
    except ValueError:
        before_seq = 0
    workspace_id = str(request.query.get("workspace_id", "") or "").strip()
    try:
        limit = max(1, min(100, int(request.query.get("limit", "50"))))
    except ValueError:
        limit = 50
    sub = _get_substrate(config)
    try:
        # Dialog-relevant kinds (mirrors ws.js handleEvent).
        kinds = (
            "incoming.atrium_dialog",
            "outgoing.dialog",
            "outgoing.response",
        )
        ph = ",".join("?" for _ in kinds)
        params: list[object] = list(kinds)
        where_parts = []
        if before_seq > 0:
            where_parts.append("seq < ?")
            params.append(before_seq)
        if workspace_id:
            where_parts.append("COALESCE(json_extract(payload_json, '$.workspace_id'), '') = ?")
            params.append(workspace_id)
        else:
            where_parts.append("COALESCE(json_extract(payload_json, '$.workspace_id'), '') = ''")
        where_extra = ("AND " + " AND ".join(where_parts) + " ") if where_parts else ""
        rows = sub.connection.execute(
            f"SELECT seq, kind, channel, principal_id, payload_json, created_at "
            f"FROM continuity_events "
            f"WHERE kind IN ({ph}) AND private = 0 "
            f"{where_extra}"
            f"ORDER BY seq DESC LIMIT ?",
            (*params, limit + 1),
        ).fetchall()
        has_more = len(rows) > limit
        rows = rows[:limit]
        events = []
        for r in reversed(rows):
            try:
                payload = json.loads(r[4] or "{}")
            except Exception:
                payload = {}
            events.append({
                "seq": r[0],
                "kind": r[1],
                "channel": r[2] or "",
                "principal_id": r[3],
                "ts": r[5],
                "text": payload.get("text", "") if isinstance(payload, dict) else "",
                "payload": payload,
            })
        return _atrium_cors(web.json_response({
            "events": events,
            "has_more": has_more,
            "before_seq": before_seq,
            "workspace_id": workspace_id,
        }))
    finally:
        sub.close()


async def atrium_events_history(request: web.Request) -> web.Response:
    """Paginated non-private Atrium event history for the reason-stream pane.

    WebSocket catch-up intentionally sends only a bounded recent tail. This
    endpoint is the slower scroll-up path for older logs.
    """
    config = request.app["config"]
    admin_password = request.app.get("admin_password", "")
    token = request.headers.get("X-Atrium-Token", "") or request.query.get("token", "")
    if admin_password and token != admin_password:
        return _atrium_cors(web.json_response({"error": "auth"}, status=401))
    try:
        before_seq = int(request.query.get("before_seq", "0"))
    except ValueError:
        before_seq = 0
    try:
        limit = max(1, min(100, int(request.query.get("limit", "80"))))
    except ValueError:
        limit = 80
    channel_filter = str(request.query.get("channel", "") or "").strip()
    session_filter = str(request.query.get("session_id", "") or "").strip()
    sub = _get_substrate(config)
    try:
        params: list[object] = []
        where_parts = ["private = 0"]
        if before_seq > 0:
            where_parts.append("seq < ?")
            params.append(before_seq)
        if channel_filter:
            where_parts.append("channel = ?")
            params.append(channel_filter)
        rows = sub.connection.execute(
            "SELECT seq, kind, principal_id, payload_json, channel, private, created_at "
            "FROM continuity_events "
            f"WHERE {' AND '.join(where_parts)} "
            "ORDER BY seq DESC LIMIT ?",
            (*params, limit + 1),
        ).fetchall()
        events = []
        for row in rows:
            try:
                payload = json.loads(row[3] or "{}")
            except Exception:
                payload = {}
            if session_filter and isinstance(payload, dict) and payload.get("session_id") != session_filter:
                continue
            ev = type("_AtriumEvent", (), {
                "seq": int(row[0]),
                "kind": row[1],
                "principal_id": row[2],
                "payload": payload,
                "channel": row[4] or "",
                "private": bool(row[5]),
                "created_at": row[6],
            })()
            events.append(_atrium_event_to_json(ev))
            if len(events) >= limit:
                break
        events.reverse()
        return _atrium_cors(web.json_response({
            "events": events,
            "has_more": len(rows) > limit,
            "before_seq": before_seq,
        }))
    finally:
        sub.close()


def _atrium_max_upload_bytes() -> int:
    raw_bytes = os.environ.get("SONYA_ATRIUM_MAX_UPLOAD_BYTES", "").strip()
    raw_mb = os.environ.get("SONYA_ATRIUM_MAX_UPLOAD_MB", "2048").strip()
    try:
        value = int(raw_bytes) if raw_bytes else int(raw_mb) * 1024 * 1024
    except ValueError:
        value = 2048 * 1024 * 1024
    return max(1, min(value, 16 * 1024 * 1024 * 1024))


async def atrium_upload(request: web.Request) -> web.Response:
    """Accept a file attachment from the Atrium composer (multipart/form-data).

    Saves the bytes into config.media_dir and returns a reference the composer
    posts back to /api/atrium/dialog as `attachments`. Files are served back
    via /api/atrium/media/{name}.

    Field: `file` (the binary). Optional `kind` (human label like "видео").
    """
    config = request.app["config"]
    admin_password = request.app.get("admin_password", "")
    token = request.headers.get("X-Atrium-Token", "") or request.query.get("token", "")
    if admin_password and token != admin_password:
        return _atrium_cors(web.json_response({"error": "auth"}, status=401))

    import os
    import uuid
    import mimetypes
    from pathlib import Path

    media_dir = Path(config.media_dir)
    media_dir.mkdir(parents=True, exist_ok=True)

    try:
        reader = await request.multipart()
    except Exception as e:
        return _atrium_cors(web.json_response({"error": f"multipart required: {e}"}, status=400))

    filename = None
    content_type = None
    kind_label = None
    workspace_id = ""
    saved_path = None
    staged_path = None
    total = 0
    max_bytes = _atrium_max_upload_bytes()

    async for part in reader:
        if part.name == "kind":
            kind_label = (await part.text()).strip() or None
            continue
        if part.name == "workspace_id":
            workspace_id = (await part.text()).strip()
            continue
        if part.name == "file":
            if staged_path is not None:
                staged_path.unlink(missing_ok=True)
                return _atrium_cors(web.json_response(
                    {"error": "only one file field is supported"}, status=400))
            filename = part.filename or "upload.bin"
            content_type = part.headers.get("Content-Type") or mimetypes.guess_type(filename)[0]
            ext = os.path.splitext(filename)[1].lower() or ""
            # Sanitize extension (alnum + dot only).
            if not ext or len(ext) > 8 or not ext[1:].isalnum():
                guessed = mimetypes.guess_extension(content_type or "") or ".bin"
                ext = guessed
            safe_name = f"atrium_{uuid.uuid4().hex}{ext}"
            saved_path = media_dir / safe_name
            staged_path = media_dir / f".{safe_name}.part"
            try:
                with open(staged_path, "xb") as f:
                    while True:
                        chunk = await part.read_chunk()
                        if not chunk:
                            break
                        total += len(chunk)
                        if total > max_bytes:
                            return _atrium_cors(web.json_response(
                                {"error": f"file too large (max {max_bytes} bytes)"},
                                status=413))
                        f.write(chunk)
            except BaseException:
                staged_path.unlink(missing_ok=True)
                raise
            finally:
                if total > max_bytes and staged_path is not None:
                    staged_path.unlink(missing_ok=True)
            continue

    if not saved_path or not staged_path or total == 0:
        if staged_path is not None:
            staged_path.unlink(missing_ok=True)
        return _atrium_cors(web.json_response({"error": "no file field"}, status=400))

    if workspace_id:
        try:
            sub = _get_substrate(config)
            try:
                from sonya.project import ProjectStore
                from sonya.project.model import ProjectNotFoundError
                try:
                    ProjectStore(sub).get(workspace_id)
                except ProjectNotFoundError:
                    staged_path.unlink(missing_ok=True)
                    return _atrium_cors(web.json_response(
                        {"error": "workspace not found"}, status=404))
            finally:
                sub.close()
        except BaseException:
            staged_path.unlink(missing_ok=True)
            raise

    try:
        staged_path.replace(saved_path)
    except BaseException:
        staged_path.unlink(missing_ok=True)
        raise

    if not content_type:
        content_type = "application/octet-stream"
    # Derive a human kind label from mime if not given.
    if not kind_label:
        if content_type.startswith("image/gif"):
            kind_label = "гифка"
        elif content_type.startswith("image/"):
            kind_label = "картинка"
        elif content_type.startswith("video/"):
            kind_label = "видео"
        elif content_type.startswith("audio/"):
            kind_label = "аудио"
        elif content_type.startswith("text/") or content_type in ("application/json",):
            kind_label = "текст"
        else:
            kind_label = "файл"

    result = {
        "ok": True,
        "name": saved_path.name,
        "orig_name": filename,
        "media_path": str(saved_path),
        "media_mime": content_type,
        "media_kind": kind_label,
        "size": total,
        "url": f"/api/atrium/media/{saved_path.name}",
    }
    if workspace_id:
        result["workspace_id"] = workspace_id
    return _atrium_cors(web.json_response(result))


async def atrium_media_get(request: web.Request) -> web.Response:
    """Serve a media file from config.media_dir by name. Used by the Atrium UI
    to render her attachments and Ivan's uploads (images/video/gif inline)."""
    config = request.app["config"]
    admin_password = request.app.get("admin_password", "")
    token = request.headers.get("X-Atrium-Token", "") or request.query.get("token", "")
    if admin_password and token != admin_password:
        return _atrium_cors(web.json_response({"error": "auth"}, status=401))

    import mimetypes
    from pathlib import Path

    name = request.match_info.get("name", "")
    # No path traversal: only a bare filename is allowed.
    if not name or "/" in name or "\\" in name or ".." in name:
        return _atrium_cors(web.json_response({"error": "bad name"}, status=400))
    media_dir = Path(config.media_dir).resolve()
    p = (media_dir / name).resolve()
    try:
        p.relative_to(media_dir)
    except ValueError:
        return _atrium_cors(web.json_response({"error": "path escape"}, status=400))
    if not p.exists() or not p.is_file():
        return _atrium_cors(web.json_response({"error": "not found"}, status=404))
    ctype = mimetypes.guess_type(str(p))[0] or "application/octet-stream"
    resp = web.FileResponse(p)
    resp.headers["Content-Type"] = ctype
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


async def atrium_heartbeat(request: web.Request) -> web.Response:
    """HTTP heartbeat (T1.5) — Atrium tells the backend it's alive.

    Writes `atrium_last_seen` (ISO ts) into technical runtime state. OutboundGate
    reads it to decide whether TG should act as fallback: when Atrium has been
    seen recently, `chat.dialog` stays Atrium-only (TG suppressed) if
    `SONYA_TG_EMERGENCY_MODE=1`. When Atrium has been silent past the
    threshold, TG resumes as the dialog channel.

    Also called implicitly by the WS feed loop, but the explicit endpoint lets
    the UI heartbeat even when no events are flowing.
    """
    config = request.app["config"]
    admin_password = request.app.get("admin_password", "")
    token = request.headers.get("X-Atrium-Token", "") or request.query.get("token", "")
    if admin_password and token != admin_password:
        return _atrium_cors(web.json_response({"error": "auth"}, status=401))
    sub = _get_substrate_writable(config)
    try:
        _atrium_mark_seen(sub)
        return _atrium_cors(web.json_response({"status": "ok"}))
    finally:
        sub.close()


def _atrium_mark_seen(sub) -> None:
    """Record that Atrium is connected right now (technical runtime state)."""
    from datetime import datetime, timezone
    from sonya.state.runtime_state import RuntimeStateStore
    try:
        RuntimeStateStore(sub).set("atrium_last_seen", datetime.now(timezone.utc).isoformat())
    except Exception:
        pass


def create_app() -> web.Application:
    config = load_config()
    import os
    admin_password = os.environ.get("SONYA_ADMIN_PASSWORD", "")
    # client_max_size: default aiohttp limit is 1 MB, which blocks file
    # attachments (video / gif / large code dumps) from the Atrium composer.
    # The upload handler streams to a staged file and enforces the configurable
    # per-file cap; allow enough multipart overhead above that cap.
    app = web.Application(
        middlewares=[security_headers_middleware, cors_middleware, auth_middleware],
        client_max_size=_atrium_max_upload_bytes() + 8 * 1024 * 1024,
    )
    app["config"] = config
    app["admin_password"] = admin_password
    app["atrium_ws_tickets"] = {}
    app.router.add_get("/", handle_index)
    app.router.add_get("/atrium", handle_atrium_redirect)
    app.router.add_get("/atrium/feed", atrium_feed_ws)
    app.router.add_get("/atrium/{path:.*}", handle_atrium_app)
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
    app.router.add_post("/api/selfmod/{proposal_id}/archive", api_selfmod_archive)
    app.router.add_post("/api/selfmod/clear-archived", api_selfmod_clear_archived)
    # Providers (key pool management)
    app.router.add_get("/api/providers", api_providers_get)
    app.router.add_post("/api/providers/registry", api_providers_registry_upsert)
    app.router.add_post("/api/providers/registry/{provider_id}", api_providers_registry_upsert)
    app.router.add_post("/api/providers/registry/{provider_id}/refresh", api_providers_registry_refresh)
    app.router.add_post("/api/providers/registry/{provider_id}/delete", api_providers_registry_delete)
    app.router.add_post("/api/providers/accounts", api_providers_accounts_add)
    app.router.add_post("/api/providers/accounts/offerings", api_providers_account_offering_set)
    app.router.add_put("/api/providers/accounts/{account_id}/secret", api_providers_account_secret_ingest)
    app.router.add_post("/api/providers/accounts/{account_id}", api_providers_accounts_update)
    app.router.add_post("/api/providers/accounts/{account_id}/delete", api_providers_accounts_delete)
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
    app.router.add_get("/api/tasks/{item_id}", api_task_detail)
    app.router.add_delete("/api/tasks/{item_id}", api_tasks_delete)
    # Approvals (shell.run / pip.install / governed selfmod gates)
    app.router.add_get("/api/approvals", api_approvals_get)
    app.router.add_post("/api/approvals/{request_id}/{decision}", api_approvals_decide)
    # Operator panel (live cognitive view + intervention)
    app.router.add_get("/api/operator/snapshot", api_operator_snapshot)
    app.router.add_get("/api/operator/live", api_operator_live_steps)
    app.router.add_post("/api/operator/trigger-active", api_operator_trigger_active)
    app.router.add_post("/api/operator/inject-message", api_operator_inject_message)
    app.router.add_post("/api/operator/task/{item_id}/action", api_operator_task_action)
    # Atrium (multichannel UI/output package — Этап 0)
    app.router.add_post("/api/atrium/ws-ticket", atrium_ws_ticket)
    app.router.add_options("/api/atrium/ws-ticket", atrium_options)
    app.router.add_post("/api/atrium/nudge", atrium_nudge)
    app.router.add_options("/api/atrium/nudge", atrium_options)
    # Atrium Этап 1 — dialog composer (T1.4) + connection heartbeat (T1.5)
    app.router.add_post("/api/atrium/dialog", atrium_dialog)
    app.router.add_options("/api/atrium/dialog", atrium_options)
    app.router.add_post("/api/atrium/heartbeat", atrium_heartbeat)
    app.router.add_options("/api/atrium/heartbeat", atrium_options)
    # Atrium media: upload (attachments from composer) + serve (her media / Ivan's).
    app.router.add_post("/api/atrium/upload", atrium_upload)
    app.router.add_options("/api/atrium/upload", atrium_options)
    app.router.add_get("/api/atrium/media/{name}", atrium_media_get)
    # Atrium dialog history pagination — load older messages on scroll-up.
    app.router.add_get("/api/atrium/history", atrium_history)
    app.router.add_options("/api/atrium/history", atrium_options)
    app.router.add_get("/api/atrium/events-history", atrium_events_history)
    app.router.add_options("/api/atrium/events-history", atrium_options)
    # Workshop — Skills / Tools-plugins / Packages browser+editor for Atrium UI.
    from sonya.admin.workshop import register_routes as _register_workshop
    _register_workshop(app)
    # Repo control — git status/commit/push/revert for the Atrium Console.
    from sonya.admin.repo import register_routes as _register_repo
    _register_repo(app)
    # Project runtime API — Atrium hosted web workspace
    from sonya.admin.project_api import register_project_routes as _register_projects
    _register_projects(app)
    return app



def main() -> None:
    app = create_app()
    host = os.environ.get("SONYA_ADMIN_HOST", "0.0.0.0")
    port = int(os.environ.get("SONYA_ADMIN_PORT", "8877"))
    print(f"Sonya Admin: http://{host}:{port}")
    web.run_app(app, host=host, port=port)
