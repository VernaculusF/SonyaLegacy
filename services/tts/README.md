# Local TTS service for Atrium

Runs a HTTP TTS server on `127.0.0.1:8878` that Atrium calls to synthesize
Sonya's voice locally on Ivan's PC.

## Phase B.1 — Silero (today)

- **Model**: Silero v4_ru — 5 RU voices, ~50 MB, real-time on CPU.
- **Voices**: `baya` (default, ж), `kseniya` (ж), `xenia` (ж), `aidar` (м), `eugene` (м).
- **Latency**: ~200ms for one short sentence on a modern i5+ (CPU-only).
- **GPU**: CUDA used automatically if available; AMD GPUs (RX 6600 XT) need
  ROCm or DirectML to engage — not required for Silero (CPU is enough).

## Phase B.2 — XTTS v2 (later — её собственный голос)

When Ivan has 5–10 минут чистой записи Сониного голоса:
1. Replace `_synthesize()` in `server.py` with XTTS v2 pipeline.
2. Same HTTP contract (`POST /tts` → WAV bytes), Atrium doesn't change.
3. AMD GPU support: install ROCm or use `torch-directml` for DX12 path.

## Setup

One-time:

```powershell
# Создаст services\tts\.venv и скачает модель (~150MB torch + 50MB silero).
powershell -ExecutionPolicy Bypass -File services\tts\setup.ps1
```

## Run

```powershell
powershell -ExecutionPolicy Bypass -File services\tts\start_tts.ps1
```

Сервис слушает только `127.0.0.1:8878` — наружу не торчит.

## Use from Atrium

1. Settings (⚙) → voice → `local`.
2. tts service url: `http://127.0.0.1:8878` (default).
3. Select voice → ▶ test voice.
4. Когда Соня отвечает в Dialog pane — ты её слышишь, рот синхронизирован
   через Web Audio AnalyserNode (реальная амплитуда WAV).

## Endpoints

- `GET  /health`  → `{ok, model, warm, default_voice, sample_rate}`
- `GET  /voices`  → `{voices: [...], default}`
- `POST /tts`     → body `{text, voice?, speed?}` → WAV bytes

## Env overrides

- `TTS_HOST` (default `127.0.0.1`)
- `TTS_PORT` (default `8878`)
- `TTS_VOICE` (default `baya`)
- `TTS_SAMPLE_RATE` (default `48000`; Silero supports 8000/24000/48000)

## Troubleshooting

- **First request slow (~5–10 sec)** — модель догружается при старте; warmup
  в `start_tts.ps1` это решает.
- **Atrium показывает `✗ Failed to fetch`** — сервис не запущен. Проверь
  `services\tts\start_tts.ps1` в отдельной консоли.
- **Голос мужской хотя выбран `baya`** — браузер закэшировал старый WAV.
  Reload вкладки.
- **AMD GPU не используется** — Silero не требует. Для XTTS v2 нужен
  `torch-directml` или ROCm — отдельный setup.
