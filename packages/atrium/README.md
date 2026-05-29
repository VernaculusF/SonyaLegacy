# Atrium

Tauri + Solid.js multichannel UI for Sonya. Этап 1 — read-only с reply.

## Status

- ✅ Layout: 3-column + collapsible reason-stream
- ✅ WS subscription к `/atrium/feed`
- ✅ Reply из reason-stream через POST `/api/atrium/nudge`
- ✅ Mind pane (focus / drives / inner thoughts / private aggregate)
- ✅ Avatar pane (статичный SVG силуэт + breathing + glow)
- ✅ Onboarding (vps host + token)
- ✅ Settings modal
- ✅ Cmd+J / Ctrl+J toggle reason-stream
- ⏳ Tauri shell (Cargo + tauri.conf.json готовы, но `cargo build` не запускался — нужен Rust toolchain)
- ⏳ Mobile layout (отдельная итерация, см. `mockups/mobile.html`)
- ⏳ Voice mode / room view (Этап 2)

## Установка

Требования:
- Node 18+
- Rust 1.70+ (для Tauri-сборки)
- На Linux: `webkit2gtk-4.1`, `libgtk-3-dev`, `libsoup-3.0-dev`
- На Windows: WebView2 Runtime (обычно уже есть)

```bash
cd packages/atrium
npm install
```

## Запуск в dev-режиме

### Browser-only (быстрая итерация UI)

```bash
npm run dev
# Откройте http://localhost:1420
```

При первом запуске введите:
- VPS host: `34.38.255.149:8877`
- Atrium token: значение `SONYA_ADMIN_PASSWORD` из `.env`

### Tauri (нативное приложение)

```bash
npm run tauri:dev
```

Запустит Vite + Rust shell + native window. Для полноценной сборки бинаря:

```bash
npm run tauri:build
```

Артефакты в `src-tauri/target/release/bundle/`.

## Архитектура

```
packages/atrium/
├── src/                    # Solid.js frontend
│   ├── main.jsx           # Entry point
│   ├── App.jsx            # Onboarding gate + main shell
│   ├── store.js           # Solid stores: settings (persisted) + feed (live)
│   ├── ws.js              # WebSocket client + reconnect + nudge HTTP
│   ├── styles.css         # Cold silver minimalism palette (см. UX_SKETCH.md §3)
│   └── components/
│       ├── Header.jsx
│       ├── AvatarPane.jsx
│       ├── DialogPane.jsx
│       ├── MindPane.jsx
│       ├── ReasonStream.jsx
│       ├── Settings.jsx
│       └── Onboarding.jsx
├── src-tauri/             # Rust shell (минимальный, только WebView host)
│   ├── Cargo.toml
│   ├── tauri.conf.json
│   ├── build.rs
│   └── src/
│       ├── main.rs
│       └── lib.rs
├── index.html             # Vite entry HTML
├── package.json
└── vite.config.js
```

## Backend интеграция

Atrium общается с Sonya через два endpoint'а в admin server:

- `ws://VPS:8877/atrium/feed?since_seq=N&token=...` — WebSocket с continuity events (фильтр по private)
- `POST http://VPS:8877/api/atrium/nudge` — reply из reason-stream pane

См. `docs/atrium/CHANNELS.md §3-§4` для protocol detail.

## Ограничения Этапа 1

- Composer **read-only** — отправка из Atrium DialogPane не реализована (нужен T1.5+ — путь в её inbox через admin API). Текущий вариант: смотрим Diagnostic, отвечаем через TG если нужно срочно.
- Avatar **статичный SVG** — Live2D подключим в Этапе 2.
- Voice mode — Этап 2 (Tauri permissions, edge-tts, whisper.cpp).
- Notifications через chime/native только в Tauri-mode (browser permissions ограничены).
