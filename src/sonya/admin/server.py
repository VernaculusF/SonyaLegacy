"""Sonya Admin Panel — local web UI for monitoring and direct chat.

Run: python -m sonya.admin
Opens on http://localhost:8877

Pages:
- /           — Dashboard (drives, counters, health)
- /thoughts   — Recent continuity events (thoughts, cognitive ticks)
- /memory     — Episodic + semantic memory viewer
- /chat       — Direct chat with Sonya's planner (full context)
- /logs       — Recent audit log entries
- /substrate  — Substrate info (version, tables, row counts)
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from sonya.config import load_config, AppConfig
from sonya.memory.episodic import EpisodicMemory
from sonya.memory.semantic import SemanticMemory
from sonya.planning import build_full_context, plan_next
from sonya.planning.memory_wiring import record_response_as_memory
from sonya.state import ContinuityStream, Substrate, SubjectStateStore
from sonya.harness.audit import AuditLog
from sonya.state.pending import PendingIntentionStore

try:
    from aiohttp import web
except ImportError:
    raise ImportError("Install aiohttp: pip install aiohttp")


_HTML_TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Sonya Admin</title>
<style>
body { font-family: monospace; background: #1a1a2e; color: #e0e0e0; margin: 20px; }
a { color: #6cf; }
h1 { color: #f06; }
h2 { color: #fc0; }
pre { background: #0f0f23; padding: 10px; border-radius: 5px; overflow-x: auto; white-space: pre-wrap; }
.thought { border-left: 3px solid #f06; padding-left: 10px; margin: 10px 0; }
.memory { border-left: 3px solid #0f6; padding-left: 10px; margin: 10px 0; }
.nav { margin-bottom: 20px; }
.nav a { margin-right: 15px; padding: 5px 10px; background: #2a2a4e; border-radius: 3px; text-decoration: none; }
textarea { width: 100%%; height: 100px; background: #0f0f23; color: #e0e0e0; border: 1px solid #444; padding: 10px; font-family: monospace; }
button { background: #f06; color: white; border: none; padding: 10px 20px; cursor: pointer; margin-top: 10px; }
.response { background: #1a2a1a; padding: 15px; border-radius: 5px; margin-top: 15px; white-space: pre-wrap; }
</style></head><body>
<div class="nav">
<a href="/">Dashboard</a>
<a href="/thoughts">Thoughts</a>
<a href="/memory">Memory</a>
<a href="/chat">Chat</a>
<a href="/logs">Audit</a>
<a href="/substrate">Substrate</a>
</div>
%s
</body></html>"""


def _get_substrate(config: AppConfig) -> Substrate:
    return Substrate.open(config.substrate_path)


async def handle_dashboard(request: web.Request) -> web.Response:
    config = request.app["config"]
    sub = _get_substrate(config)
    try:
        state = SubjectStateStore(sub).load()
        intentions = PendingIntentionStore(sub).list_active()
        stream = ContinuityStream(sub)
        latest_seq = stream.latest_seq()

        body = f"<h1>Sonya Dashboard</h1>"
        body += f"<h2>Subject State</h2><pre>{json.dumps({'active_principal': state.active_principal_id, 'emotional_vector': state.emotional_vector, 'drift_signals': list(state.drift_signals), 'pending_intentions': list(state.pending_intentions)}, ensure_ascii=False, indent=2)}</pre>"
        body += f"<h2>Active Intentions ({len(intentions)})</h2>"
        for i in intentions:
            body += f"<div class='memory'>{i.intention_id}: {i.description} (deadline: {i.deadline})</div>"
        body += f"<h2>Continuity</h2><p>Latest seq: {latest_seq}</p>"
        body += f"<h2>Config</h2><pre>LLM API: {config.llm_api_base}\nModel: {config.llm_model}\nSubstrate: {config.substrate_path}</pre>"
    finally:
        sub.close()
    return web.Response(text=_HTML_TEMPLATE % body, content_type="text/html")


async def handle_thoughts(request: web.Request) -> web.Response:
    config = request.app["config"]
    sub = _get_substrate(config)
    try:
        stream = ContinuityStream(sub)
        latest = stream.latest_seq()
        start = max(0, latest - 50)
        events = list(stream.read_since(start))

        body = "<h1>Recent Thoughts & Events</h1>"
        for ev in reversed(events):
            kind_class = "thought" if "internal" in ev.kind else "memory"
            payload_str = json.dumps(ev.payload, ensure_ascii=False, indent=2)[:500]
            body += f"<div class='{kind_class}'><b>[{ev.seq}] {ev.kind}</b> ({ev.created_at[:19]})<pre>{payload_str}</pre></div>"
    finally:
        sub.close()
    return web.Response(text=_HTML_TEMPLATE % body, content_type="text/html")


async def handle_memory(request: web.Request) -> web.Response:
    config = request.app["config"]
    sub = _get_substrate(config)
    try:
        episodic = EpisodicMemory(sub)
        semantic = SemanticMemory(sub)
        recent = episodic.get_recent(limit=30)
        facts = semantic.get_all(limit=20)

        body = "<h1>Memory</h1><h2>Episodic (last 30)</h2>"
        for ev in recent:
            body += f"<div class='memory'><b>{ev.event_type}</b> [{ev.timestamp[:16]}] imp={ev.importance_score:.1f} ret={ev.retention_strength:.1f}<br>{ev.raw_content[:200]}</div>"
        body += "<h2>Semantic Facts</h2>"
        for f in facts:
            body += f"<div class='thought'><b>{f.fact_type}</b> (conf={f.confidence:.1f}): {f.statement}</div>"
    finally:
        sub.close()
    return web.Response(text=_HTML_TEMPLATE % body, content_type="text/html")


async def handle_chat_page(request: web.Request) -> web.Response:
    body = """<h1>Chat with Sonya</h1>
<form method="POST" action="/chat/send">
<textarea name="message" placeholder="Напиши что-нибудь..."></textarea>
<button type="submit">Send</button>
</form>"""
    return web.Response(text=_HTML_TEMPLATE % body, content_type="text/html")


async def handle_chat_send(request: web.Request) -> web.Response:
    config = request.app["config"]
    data = await request.post()
    message = data.get("message", "")
    if not message:
        return web.HTTPFound("/chat")

    sub = _get_substrate(config)
    try:
        ctx = build_full_context(
            substrate=sub,
            user_input=str(message),
            principal_id="ivan",
        )

        # Create provider
        api_key_secret = config.openrouter_api_key
        api_key = api_key_secret.get() if api_key_secret else ""

        import httpx

        class _ChatProvider:
            async def complete_text(self, messages, **kwargs):
                headers: dict[str, str] = {"Content-Type": "application/json"}
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
                async with httpx.AsyncClient(timeout=60.0) as client:
                    resp = await client.post(
                        f"{config.llm_api_base}/chat/completions",
                        headers=headers,
                        json={"model": config.llm_model, "messages": messages, "max_tokens": 1000, "temperature": 0.8},
                    )
                    resp.raise_for_status()
                    return resp.json()["choices"][0]["message"]["content"]

        response = await plan_next(ctx, _ChatProvider())
        record_response_as_memory(sub, str(message), response, channel="admin")

        body = f"""<h1>Chat with Sonya</h1>
<div class='memory'><b>Ты:</b> {message}</div>
<div class='response'><b>Соня:</b> {response.text}</div>
<form method="POST" action="/chat/send">
<textarea name="message" placeholder="..."></textarea>
<button type="submit">Send</button>
</form>"""
    finally:
        sub.close()

    return web.Response(text=_HTML_TEMPLATE % body, content_type="text/html")


async def handle_logs(request: web.Request) -> web.Response:
    config = request.app["config"]
    sub = _get_substrate(config)
    try:
        audit = AuditLog(sub)
        entries = audit.query()[-30:]

        body = "<h1>Audit Log (last 30)</h1>"
        for e in reversed(entries):
            body += f"<div class='thought'>[{e.seq}] {e.timestamp[:19]} | {e.action} | {e.decision} | scope={e.scope}</div>"
    finally:
        sub.close()
    return web.Response(text=_HTML_TEMPLATE % body, content_type="text/html")


async def handle_substrate(request: web.Request) -> web.Response:
    config = request.app["config"]
    sub = _get_substrate(config)
    try:
        version = sub.schema_version
        tables = sub.connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()

        body = f"<h1>Substrate</h1><p>Version: {version}</p><p>Path: {config.substrate_path}</p>"
        body += "<h2>Tables</h2>"
        for (name,) in tables:
            count = sub.connection.execute(f"SELECT COUNT(*) FROM [{name}]").fetchone()[0]
            body += f"<div class='memory'>{name}: {count} rows</div>"
    finally:
        sub.close()
    return web.Response(text=_HTML_TEMPLATE % body, content_type="text/html")


def create_app() -> web.Application:
    config = load_config()
    app = web.Application()
    app["config"] = config
    app.router.add_get("/", handle_dashboard)
    app.router.add_get("/thoughts", handle_thoughts)
    app.router.add_get("/memory", handle_memory)
    app.router.add_get("/chat", handle_chat_page)
    app.router.add_post("/chat/send", handle_chat_send)
    app.router.add_get("/logs", handle_logs)
    app.router.add_get("/substrate", handle_substrate)
    return app


def main() -> None:
    app = create_app()
    print("Sonya Admin: http://localhost:8877")
    web.run_app(app, host="127.0.0.1", port=8877)
