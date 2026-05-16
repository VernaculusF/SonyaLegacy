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
except ImportError:
    raise ImportError("Install aiohttp: pip install aiohttp")


def _get_substrate(config: AppConfig) -> Substrate:
    return Substrate.open(config.substrate_path)


async def handle_index(request: web.Request) -> web.Response:
    return web.Response(text=ADMIN_HTML, content_type="text/html")


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
                    if "\n" in text:
                        text = text.split("\n")[0]
                    import json as _json
                    data = _json.loads(text)
                    return data["choices"][0]["message"]["content"]

        response = await plan_next(ctx, _Provider())
        record_response_as_memory(sub, message, response, channel="admin")
        return web.json_response({"response": response.text})
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


def create_app() -> web.Application:
    config = load_config()
    app = web.Application()
    app["config"] = config
    app.router.add_get("/", handle_index)
    app.router.add_get("/api/dashboard", api_dashboard)
    app.router.add_get("/api/thoughts", api_thoughts)
    app.router.add_get("/api/memory", api_memory)
    app.router.add_post("/api/chat/send", api_chat_send)
    app.router.add_get("/api/audit", api_audit)
    app.router.add_get("/api/substrate", api_substrate)
    return app


def main() -> None:
    app = create_app()
    print("Sonya Admin: http://localhost:8877")
    web.run_app(app, host="127.0.0.1", port=8877)
