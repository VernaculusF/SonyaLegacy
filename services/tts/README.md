# Local TTS service for Atrium

Runs a HTTP TTS server on `127.0.0.1:8878` that Atrium calls to synthesize
Sonya's voice locally on Ivan's PC.

## Phase B.1.1 — Piper TTS (current)

- **Engine**: Piper (ONNX neural TTS, no torch needed at runtime).
- **Model**: 60 MB per voice, real-time on CPU (~0.25s for one sentence on i5+).
- **Voices** (Russian):
  - `irina` — Female, primary (recommended for Sonya).
  - `denis` — Male.
  - `ruslan` — Male.
- Quality: per the [alphacephei eval](https://alphacephei.com/nsh/2024/07/12/russian-tts.html)
  Piper Irina is the strongest free open-source RU voice (MOS 4.0/5).

## Phase B.2 — XTTS v2 (later — её собственный голос)

When Ivan has 5–10 минут чистой записи Сониного голоса:
1. Replace `_synthesize()` in `server.py` with XTTS v2 pipeline.
2. Same HTTP contract (`POST /tts` → WAV bytes), Atrium doesn't change.
3. AMD GPU support: install ROCm or use `torch-directml` for DX12 path.

## Setup

One-time:

```powershell
powershell -ExecutionPolicy Bypass -File services\tts\setup.ps1
```

Это создаст `services\tts\.venv` (legkий, ~80 MB), скачает 3 голосовые модели
(~180 MB) в `services\tts\.cache\piper\`.

## Run

```powershell
powershell -ExecutionPolicy Bypass -File services\tts\start_tts.ps1
```

Сервис слушает только `127.0.0.1:8878` — наружу не торчит. Holds the loaded
model in RAM (~150 MB).

## Use from Atrium

1. Settings (⚙) → voice → `local`.
2. tts service url: `http://127.0.0.1:8878` (default).
3. tts voice → выбрать `irina` (или denis / ruslan).
4. ▶ test voice.
5. Когда Соня отвечает в Dialog pane — ты её слышишь, рот синхронизирован
   через Web Audio AnalyserNode (реальная амплитуда WAV).

## Endpoints

- `GET  /health`  → `{ok, model, warm, default_voice, sample_rate, available_voices}`
- `GET  /voices`  → `{voices: [...], default, labels}`
- `POST /tts`     → body `{text, voice?, speed?}` → WAV bytes (audio/wav)

## Env overrides

- `TTS_HOST` (default `127.0.0.1`)
- `TTS_PORT` (default `8878`)
- `TTS_VOICE` (default `irina`)

## Adding more voices

Look up voices at https://huggingface.co/rhasspy/piper-voices/tree/main/ru/ru_RU,
download `<voice>.onnx` + `<voice>.onnx.json` to `services\tts\.cache\piper\`,
add an entry to `VOICE_REGISTRY` in `server.py`. Restart.

## Troubleshooting

- **Atrium показывает `✗ Failed to fetch`** — сервис не запущен. Проверь
  `services\tts\start_tts.ps1` в отдельной консоли.
- **`no russian text` 400** — модель v4_ru понимает только кириллицу. Иван
  пишет latin-only? Этот случай теперь возвращает чистый 400.
- **первый запрос медленный (~2s)** — модель греется. Server prewarms на старте.
