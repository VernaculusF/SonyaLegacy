"""Local TTS server for Atrium.

Runs on Ivan's PC at http://127.0.0.1:8878. Atrium fetches WAV bytes from
POST /tts and plays them through a Web Audio AnalyserNode for lip-sync.

Phase B.1.1 — Piper TTS (current):
  - Free, fast (~0.2s for short sentence on CPU), neural quality.
  - Russian voices: ru_RU-irina-medium (female, recommended), ru_RU-ruslan-medium (male).
  - Uses ONNX runtime — no torch needed at runtime, much smaller.
  - Models cached in services/tts/.cache/piper/*.onnx (downloaded by setup.ps1).

Phase B.2 — XTTS v2 (later, when Ivan has 5-10 min of cloned voice samples):
  - Replace _synthesize() with XTTS pipeline.
  - Same HTTP contract — Atrium doesn't change.

Endpoints:
  GET  /voices                 → {voices: [...], default}
  POST /tts                    → body {text, voice?, speed?} → WAV bytes (audio/wav)
  GET  /health                 → {ok, model, warm, default_voice, sample_rate}

CORS open (only listens on 127.0.0.1; safe by no remote access).
"""
from __future__ import annotations

import io
import logging
import os
import re
import time
import wave
from pathlib import Path

from aiohttp import web

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("tts")

_HERE = Path(__file__).parent
_MODELS_DIR = _HERE / ".cache" / "piper"

# Voice id → (model filename, label, gender). Models live under _MODELS_DIR.
# More voices: download from https://huggingface.co/rhasspy/piper-voices/tree/main/ru/ru_RU
VOICE_REGISTRY = {
    "irina":  ("ru_RU-irina-medium.onnx",  "Irina (female)",  "female"),
    "denis":  ("ru_RU-denis-medium.onnx",  "Denis (male)",    "male"),
    "ruslan": ("ru_RU-ruslan-medium.onnx", "Ruslan (male)",   "male"),
}
DEFAULT_VOICE = os.environ.get("TTS_VOICE", "irina")

_voices_cache = {}  # voice_id → PiperVoice instance


def _available_voices() -> list[str]:
    """Voice ids whose ONNX model is actually present on disk."""
    out = []
    for vid, (fname, _, _) in VOICE_REGISTRY.items():
        if (_MODELS_DIR / fname).exists():
            out.append(vid)
    return out


def _load_voice(voice_id: str):
    if voice_id in _voices_cache:
        return _voices_cache[voice_id]
    if voice_id not in VOICE_REGISTRY:
        raise ValueError(f"unknown voice {voice_id!r} (known: {list(VOICE_REGISTRY)})")
    fname, label, _ = VOICE_REGISTRY[voice_id]
    model_path = _MODELS_DIR / fname
    if not model_path.exists():
        raise FileNotFoundError(
            f"voice model not found: {model_path}. "
            f"Run services\\tts\\setup.ps1 to download."
        )
    log.info("loading Piper voice %s (%s) ...", voice_id, label)
    t0 = time.time()
    from piper import PiperVoice
    v = PiperVoice.load(str(model_path))
    log.info("voice %s loaded in %.1fs (sample_rate=%d)",
             voice_id, time.time() - t0, v.config.sample_rate)
    _voices_cache[voice_id] = v
    return v


def _synthesize(text: str, voice_id: str, speed: float = 1.0) -> bytes:
    """Synthesize text → WAV bytes (PCM16 mono @ voice's native sample rate)."""
    text = (text or "").strip()
    if not text:
        raise ValueError("empty text")
    # Russian-only check (Piper can handle other text but ru models are tuned for ru).
    if not re.search(r"[а-яёА-ЯЁ]", text):
        raise ValueError("no russian text")
    v = _load_voice(voice_id)
    buf = io.BytesIO()
    # Piper writes a complete WAV (header + frames) using the wave module.
    from piper import SynthesisConfig
    cfg = None
    if speed and speed > 0 and speed != 1.0:
        # Piper length_scale: <1 faster, >1 slower (inverse of speed).
        try:
            cfg = SynthesisConfig(length_scale=1.0 / speed)
        except Exception:
            cfg = None
    with wave.open(buf, "wb") as wf:
        if cfg is not None:
            v.synthesize_wav(text, wf, syn_config=cfg)
        else:
            v.synthesize_wav(text, wf)
    return buf.getvalue()


# ----- HTTP handlers -----

def _cors(resp: web.Response) -> web.Response:
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp


async def health(request: web.Request) -> web.Response:
    available = _available_voices()
    sr = None
    if _voices_cache:
        sr = next(iter(_voices_cache.values())).config.sample_rate
    return _cors(web.json_response({
        "ok": True,
        "model": "piper",
        "warm": bool(_voices_cache),
        "default_voice": DEFAULT_VOICE if DEFAULT_VOICE in available else (available[0] if available else None),
        "sample_rate": sr,
        "available_voices": available,
    }))


async def voices(request: web.Request) -> web.Response:
    available = _available_voices()
    return _cors(web.json_response({
        "voices": available,
        "default": DEFAULT_VOICE if DEFAULT_VOICE in available else (available[0] if available else None),
        "labels": {vid: VOICE_REGISTRY[vid][1] for vid in available},
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
    text = text[:1500]
    t0 = time.time()
    try:
        wav_bytes = _synthesize(text, voice, speed=speed)
    except FileNotFoundError as e:
        return _cors(web.json_response({"error": str(e)}, status=404))
    except ValueError as e:
        return _cors(web.json_response({"error": str(e)}, status=400))
    except Exception as e:
        log.exception("synth failed")
        return _cors(web.json_response({"error": f"{type(e).__name__}: {e}"}, status=500))
    log.info("tts %d chars / %s / %.2fs → %d bytes",
             len(text), voice, time.time() - t0, len(wav_bytes))
    resp = web.Response(body=wav_bytes, content_type="audio/wav")
    resp.headers["X-TTS-Voice"] = voice
    resp.headers["X-TTS-Latency"] = f"{(time.time() - t0):.3f}"
    return _cors(resp)


async def options_handler(request: web.Request) -> web.Response:
    return _cors(web.Response(status=204))


def make_app() -> web.Application:
    app = web.Application(client_max_size=1 << 20)
    app.router.add_get("/health", health)
    app.router.add_get("/voices", voices)
    app.router.add_post("/tts", tts)
    for path in ("/health", "/voices", "/tts"):
        app.router.add_options(path, options_handler)
    return app


def main():
    host = os.environ.get("TTS_HOST", "127.0.0.1")
    port = int(os.environ.get("TTS_PORT", "8878"))
    available = _available_voices()
    if not available:
        log.error("no voice models found in %s — run setup.ps1 to download.", _MODELS_DIR)
    else:
        log.info("available voices: %s", ", ".join(available))
        # Warm the default voice so first request isn't slow.
        try:
            warm = DEFAULT_VOICE if DEFAULT_VOICE in available else available[0]
            _load_voice(warm)
        except Exception:
            log.exception("warmup failed; voice will lazy-load on first request")
    log.info("starting TTS server on http://%s:%d", host, port)
    web.run_app(make_app(), host=host, port=port)


if __name__ == "__main__":
    main()
