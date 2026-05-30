"""Local TTS server for Atrium.

Runs on Ivan's PC at http://127.0.0.1:8878. Atrium fetches WAV bytes from
POST /tts and plays them through a Web Audio AnalyserNode for lip-sync.

Phase B.1 — Silero TTS:
  - Free, ~50MB model, 4 Russian voices (3 female, 1 male).
  - Real-time on CPU (i5+ ~200ms for one sentence).
  - No GPU needed → works today on Ivan's RX 6600 XT box without ROCm setup.

Phase B.2 — XTTS v2 (later, when Ivan wants HER voice):
  - Replace _synthesize() with XTTS pipeline.
  - Same HTTP contract — Atrium doesn't change.

Endpoints:
  GET  /voices                 → {voices: [...], default: "baya"}
  POST /tts                    → body {text, voice?, speed?} → WAV bytes (audio/wav)
  GET  /health                 → {ok: true, model: "silero-v4-ru", warm: bool}

CORS open (only listens on 127.0.0.1; safe by virtue of no remote access).
"""
from __future__ import annotations

import io
import logging
import os
import time
from pathlib import Path
from typing import Any

import torch
from aiohttp import web

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("tts")

# Silero v4 Russian model — 4 voices: aidar (m), baya (f), kseniya (f), xenia (f), eugene (m)
SILERO_LANG = "ru"
SILERO_MODEL_ID = "v4_ru"
DEFAULT_VOICE = os.environ.get("TTS_VOICE", "baya")
SAMPLE_RATE = int(os.environ.get("TTS_SAMPLE_RATE", "48000"))
PUT_ACCENT = True
PUT_YO = True

# Where Silero caches its weights — use a local cache dir to avoid re-download.
_CACHE_DIR = Path(__file__).parent / ".cache"
_CACHE_DIR.mkdir(exist_ok=True)
torch.hub.set_dir(str(_CACHE_DIR))

_model = None  # lazy-loaded on first /tts


def _load_model():
    global _model
    if _model is not None:
        return _model
    log.info("loading Silero %s/%s ...", SILERO_LANG, SILERO_MODEL_ID)
    t0 = time.time()
    model, _ = torch.hub.load(
        repo_or_dir="snakers4/silero-models",
        model="silero_tts",
        language=SILERO_LANG,
        speaker=SILERO_MODEL_ID,
        trust_repo=True,
    )
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model.to(device)
    log.info("model loaded on %s in %.1fs (voices: %s)",
             device, time.time() - t0, ", ".join(model.speakers))
    _model = model
    return model


def _synthesize(text: str, voice: str, speed: float = 1.0) -> bytes:
    """Run Silero TTS and return WAV bytes (PCM16 mono @ SAMPLE_RATE)."""
    import wave
    model = _load_model()
    if voice not in model.speakers:
        log.warning("voice %r not in %s — using default %r", voice, model.speakers, DEFAULT_VOICE)
        voice = DEFAULT_VOICE
    # Silero accepts plain text; it does its own G2P. Strip noise.
    text = (text or "").strip()
    if not text:
        raise ValueError("empty text")
    # Silero v4_ru only accepts Russian letters + basic punct. If the input
    # has no Russian content (English-only / numbers / mojibake), Silero's
    # process_simple_text raises ValueError without a message. Pre-flight
    # check so we return a clean 400.
    import re
    if not re.search(r"[а-яёА-ЯЁ]", text):
        raise ValueError("no russian text (silero v4_ru is RU-only)")
    audio = model.apply_tts(
        text=text,
        speaker=voice,
        sample_rate=SAMPLE_RATE,
        put_accent=PUT_ACCENT,
        put_yo=PUT_YO,
    )
    # audio is a torch.float32 tensor on the model's device, range -1..1.
    pcm = (audio.detach().cpu().clamp(-1.0, 1.0).numpy() * 32767).astype("int16")
    if speed != 1.0 and 0.5 <= speed <= 2.0:
        # crude resample for speed change — fine for small adjustments
        import numpy as np
        idx = (np.arange(int(len(pcm) / speed)) * speed).astype("int64")
        idx = idx[idx < len(pcm)]
        pcm = pcm[idx]
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)  # 16-bit
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(pcm.tobytes())
    return buf.getvalue()


# ----- HTTP handlers -----

def _cors(resp: web.Response) -> web.Response:
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp


async def health(request: web.Request) -> web.Response:
    return _cors(web.json_response({
        "ok": True,
        "model": f"silero-{SILERO_MODEL_ID}",
        "warm": _model is not None,
        "default_voice": DEFAULT_VOICE,
        "sample_rate": SAMPLE_RATE,
    }))


async def voices(request: web.Request) -> web.Response:
    model = _load_model()
    return _cors(web.json_response({
        "voices": list(model.speakers),
        "default": DEFAULT_VOICE,
    }))


async def tts(request: web.Request) -> web.Response:
    try:
        data = await request.json()
    except Exception:
        return _cors(web.json_response({"error": "json body required"}, status=400))
    text = str(data.get("text") or "").strip()
    voice = str(data.get("voice") or DEFAULT_VOICE).strip() or DEFAULT_VOICE
    try:
        speed = float(data.get("speed") or 1.0)
    except Exception:
        speed = 1.0
    if not text:
        return _cors(web.json_response({"error": "text required"}, status=400))
    # Silero choke-points: very long input crashes. Hard cap at 1000 chars.
    text = text[:1000]
    t0 = time.time()
    try:
        wav_bytes = _synthesize(text, voice, speed=speed)
    except Exception as e:
        log.exception("synth failed")
        return _cors(web.json_response({"error": f"{type(e).__name__}: {e}"}, status=500))
    log.info("tts %d chars / %s / %.1fs → %d bytes",
             len(text), voice, time.time() - t0, len(wav_bytes))
    resp = web.Response(body=wav_bytes, content_type="audio/wav")
    resp.headers["X-TTS-Voice"] = voice
    resp.headers["X-TTS-Latency"] = f"{(time.time() - t0):.3f}"
    return _cors(resp)


async def options_handler(request: web.Request) -> web.Response:
    return _cors(web.Response(status=204))


def make_app() -> web.Application:
    app = web.Application(client_max_size=1 << 20)  # 1 MB max body
    app.router.add_get("/health", health)
    app.router.add_get("/voices", voices)
    app.router.add_post("/tts", tts)
    for path in ("/health", "/voices", "/tts"):
        app.router.add_options(path, options_handler)
    return app


def main():
    host = os.environ.get("TTS_HOST", "127.0.0.1")
    port = int(os.environ.get("TTS_PORT", "8878"))
    # warm the model on startup to avoid first-request stall
    try:
        _load_model()
    except Exception:
        log.exception("warmup failed; model will lazy-load on first request")
    log.info("starting TTS server on http://%s:%d", host, port)
    web.run_app(make_app(), host=host, port=port)


if __name__ == "__main__":
    main()
