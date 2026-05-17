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
    return Substrate.open(config.substrate_path)


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


# --- Core process management ---

_core_process: Any = None


async def api_core_status(request: web.Request) -> web.Response:
    """Check if core process is running."""
    global _core_process
    running = _core_process is not None and _core_process.returncode is None
    return web.json_response({"running": running, "pid": _core_process.pid if running else None})


async def api_core_start(request: web.Request) -> web.Response:
    """Start the core process (sonya main with userbot + thinking).

    Query params:
      mode = full | telegram_only | thinking_only (default: full)
    """
    import subprocess
    import os
    global _core_process

    # Check if already running
    if _core_process is not None and _core_process.returncode is None:
        return web.json_response({"status": "already_running", "pid": _core_process.pid})

    mode = request.query.get("mode", "full")

    # Build env with PYTHONPATH and toggles
    env = os.environ.copy()
    project_root = os.path.expanduser("~/Sonya")
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

    # Start core as subprocess
    _core_process = subprocess.Popen(
        [os.path.expanduser("~/Sonya/.venv/bin/python"), "-m", "sonya"],
        cwd=project_root,
        env=env,
        stdout=open("/tmp/sonya.log", "w"),
        stderr=subprocess.STDOUT,
    )
    return web.json_response({"status": "started", "pid": _core_process.pid, "mode": mode})


async def api_core_stop(request: web.Request) -> web.Response:
    """Stop the core process."""
    import signal
    global _core_process

    if _core_process is None or _core_process.returncode is not None:
        return web.json_response({"status": "not_running"})

    _core_process.send_signal(signal.SIGKILL)
    _core_process.wait(timeout=5)
    pid = _core_process.pid
    _core_process = None
    return web.json_response({"status": "stopped", "pid": pid})


async def api_core_logs(request: web.Request) -> web.Response:
    """Get last N lines of core log."""
    import os
    lines = int(request.query.get("lines", "50"))
    log_path = "/tmp/sonya.log"
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
    return app


def main() -> None:
    app = create_app()
    print("Sonya Admin: http://0.0.0.0:8877")
    web.run_app(app, host="0.0.0.0", port=8877)
