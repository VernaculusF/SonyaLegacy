"""TTS proxy for Atrium — ElevenLabs Text-to-Speech.

Atrium UI hits `POST /api/atrium/tts` with `{text, voice_id?, model_id?}`,
this server adds the X-API-Key (held in env, never exposed to the browser)
and forwards to ElevenLabs, streaming the resulting audio (mpeg) back.

Key safety:
  - API key in env var ELEVENLABS_API_KEY only (deploy/update.sh ensures
    it's loaded from .env on the VPS).
  - Atrium auth via X-Atrium-Token (same as other /api/atrium/* endpoints).
  - Voice ID is parameter — Ivan can pick any voice from the library.

Endpoints:
  GET  /api/atrium/tts/health   — quota + key presence
  POST /api/atrium/tts          — body {text, voice_id?, model_id?, voice_settings?}
                                   → audio/mpeg bytes (MP3, 44.1k mono)
"""
from __future__ import annotations

import logging
import os
from typing import Any

import aiohttp
from aiohttp import web

log = logging.getLogger("sonya.admin.tts")

ELEVENLABS_BASE = "https://api.elevenlabs.io/v1"
DEFAULT_MODEL = "eleven_multilingual_v2"  # supports Russian
DEFAULT_VOICE_ID = "0ArNnoIAWKlT4WweaVMY"  # Ivan's chosen voice (RU female)


def _check_auth(request: web.Request) -> str | None:
    admin_password = request.app.get("admin_password", "")
    token = request.headers.get("X-Atrium-Token", "") or request.query.get("token", "")
    if admin_password and token != admin_password:
        return "auth"
    return None


def _cors(resp: web.StreamResponse) -> web.StreamResponse:
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type, X-Atrium-Token"
    return resp


def _api_key() -> str:
    return os.environ.get("ELEVENLABS_API_KEY", "").strip()


async def tts_options(request: web.Request) -> web.Response:
    return _cors(web.Response(status=204))


async def tts_health(request: web.Request) -> web.Response:
    """Report whether the API key is set and (optionally) probe quota."""
    if (err := _check_auth(request)):
        return _cors(web.json_response({"error": err}, status=401))
    key = _api_key()
    if not key:
        return _cors(web.json_response({
            "ok": False,
            "configured": False,
            "error": "ELEVENLABS_API_KEY not set on server",
        }))
    # Probe /v1/user/subscription for quota info.
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{ELEVENLABS_BASE}/user/subscription",
                headers={"xi-api-key": key},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as r:
                if r.status != 200:
                    txt = await r.text()
                    return _cors(web.json_response({
                        "ok": False,
                        "configured": True,
                        "error": f"elevenlabs {r.status}: {txt[:200]}",
                    }))
                sub = await r.json()
        return _cors(web.json_response({
            "ok": True,
            "configured": True,
            "tier": sub.get("tier"),
            "char_count": sub.get("character_count"),
            "char_limit": sub.get("character_limit"),
            "next_reset": sub.get("next_character_count_reset_unix"),
        }))
    except Exception as e:
        return _cors(web.json_response({
            "ok": False,
            "configured": True,
            "error": f"probe failed: {type(e).__name__}: {e}",
        }))


async def tts_synth(request: web.Request) -> web.StreamResponse:
    """Synthesize text via ElevenLabs and stream MP3 back to Atrium.

    Body: {text, voice_id?, model_id?, voice_settings?}
    Response: audio/mpeg (raw MP3 bytes).

    We use the streaming endpoint so the first audio bytes arrive
    quickly (~200-400ms) and we can pipe straight to the browser.
    """
    if (err := _check_auth(request)):
        return _cors(web.json_response({"error": err}, status=401))
    key = _api_key()
    if not key:
        return _cors(web.json_response(
            {"error": "ELEVENLABS_API_KEY not set on server"}, status=503))
    try:
        data = await request.json()
    except Exception:
        return _cors(web.json_response({"error": "json body required"}, status=400))
    text = str(data.get("text") or "").strip()
    if not text:
        return _cors(web.json_response({"error": "text required"}, status=400))
    voice_id = str(data.get("voice_id") or DEFAULT_VOICE_ID).strip() or DEFAULT_VOICE_ID
    model_id = str(data.get("model_id") or DEFAULT_MODEL).strip() or DEFAULT_MODEL
    voice_settings = data.get("voice_settings") or {
        "stability": 0.40,
        "similarity_boost": 0.85,
        "style": 0.20,
        "use_speaker_boost": True,
    }
    # Sane caps to avoid blowing the quota by accident.
    text = text[:2000]
    payload = {
        "text": text,
        "model_id": model_id,
        "voice_settings": voice_settings,
    }
    url = f"{ELEVENLABS_BASE}/text-to-speech/{voice_id}/stream"
    headers = {
        "xi-api-key": key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }
    # Open upstream + stream chunks straight through.
    timeout = aiohttp.ClientTimeout(total=90, sock_read=30)
    try:
        session = aiohttp.ClientSession(timeout=timeout)
        upstream = await session.post(url, json=payload, headers=headers)
    except Exception as e:
        try:
            await session.close()
        except Exception:
            pass
        return _cors(web.json_response(
            {"error": f"upstream connect failed: {type(e).__name__}: {e}"},
            status=502,
        ))
    try:
        if upstream.status != 200:
            err_text = await upstream.text()
            log.warning("elevenlabs %d: %s", upstream.status, err_text[:300])
            await upstream.release()
            return _cors(web.json_response(
                {"error": f"elevenlabs {upstream.status}: {err_text[:400]}"},
                status=502,
            ))
        resp = web.StreamResponse(status=200, headers={
            "Content-Type": "audio/mpeg",
            "Cache-Control": "no-store",
            "X-TTS-Voice": voice_id,
            "X-TTS-Model": model_id,
        })
        _cors(resp)
        await resp.prepare(request)
        async for chunk in upstream.content.iter_chunked(8192):
            await resp.write(chunk)
        await resp.write_eof()
        return resp
    finally:
        try:
            await upstream.release()
        except Exception:
            pass
        try:
            await session.close()
        except Exception:
            pass


def register_routes(app: web.Application) -> None:
    app.router.add_get("/api/atrium/tts/health", tts_health)
    app.router.add_post("/api/atrium/tts", tts_synth)
    app.router.add_options("/api/atrium/tts", tts_options)
    app.router.add_options("/api/atrium/tts/health", tts_options)
