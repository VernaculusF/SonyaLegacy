# VPS Operations — Sonya Hosting

**Status:** Active
**Type:** Operations
**Last updated:** 2026-06-10

## Current provider operations

LLM calls use the substrate-owned provider registry, accounts, account
offerings, and model pools. Provider-account credentials are encrypted and must
be added or rotated only through Admin Providers protected secret ingestion.
Legacy `provider_keys` references later in this file describe compatibility
data, not the current management path. Environment configuration must not bind
Sonya to a provider or model.

## 1. Где хостится

- **Provider:** Google Cloud Platform (GCE)
- **Instance:** `instance-20260516-063101`
- **Zone:** `europe-west1-b` (Belgium)
- **Machine:** e2-custom (4 vCPU / 8 GB RAM)
- **OS:** Debian 12
- **External IP:** `34.38.255.149`
- **Disk:** 50 GB Balanced Persistent Disk
- **Budget:** $300 free credits (expires ~August 2026)

## 2. Что там работает

| Service / Container | Port | Описание |
|---------------------|------|----------|
| `sonya.service` (systemd) | — | Ядро: substrate + thinking loop + telegram userbot + embedding indexer |
| `sonya-admin.service` (systemd) | 8877 | Web-панель (пароль в .env) + Atrium WS feed `/atrium/feed` + nudge `/api/atrium/nudge` |
| `sonya-searxng` (docker) | 127.0.0.1:8888 | Self-hosted SearXNG — meta-search для `web.search` |

LLM-вызовы идут напрямую через `sonya.providers.llm_provider` с собственной key pool в substrate (provider_keys table). OmniRoute удалён.

## 3. SSH доступ

```bash
ssh jester-sonya@34.38.255.149
```

Single user account (`jester-sonya`) с sudo. Sonya сервисы тоже работают под этим юзером.

## 4. Файловая структура на сервере

```
/home/jester-sonya/
├── Sonya/                          — проект (git clone https://github.com/VernaculusF/Sonya, branch=develop)
│   ├── src/sonya/                  — ядро
│   ├── packages/tg-userbot/        — Telethon channel adapter (auto-discovered)
│   │   └── src/tg_userbot/
│   │       ├── channel.py          — TelegramChannel + media download + group rules
│   │       └── sticker_store.py    — capture+resend stickers
│   ├── deploy/
│   │   ├── update.sh               — git pull + pip + systemctl restart
│   │   ├── searxng/
│   │   │   ├── setup.sh            — Docker setup для SearXNG (idempotent)
│   │   │   └── settings.yml        — base config (копируется в ~/.sonya/searxng/ на первом запуске)
│   │   ├── backup.sh               — substrate backup (используется cron'ом)
│   │   └── systemd/
│   │       ├── sonya.service       — core systemd unit
│   │       └── sonya-admin.service — admin systemd unit
│   ├── .env                        — конфиг (TG api id/hash, admin password, env vars)
│   ├── tg.session                  — Telegram userbot session (Telethon SQLite)
│   └── .venv/                      — Python virtual environment (Python 3.11)
│
└── .sonya/                         — runtime data root
    ├── sonya_substrate.db          — substrate (SQLite WAL; verify live schema after each deploy)
    ├── sonya_substrate.db-wal      — WAL file (live writes)
    ├── sonya_substrate.db-shm      — shared memory
    ├── knowledge/                  — её факт-база (markdown). pentest/*.md, wp/*.md и т.д.
    │                                 Пишется через knowledge.* tools, НЕ через filesystem.
    ├── media/                      — скачанные TG медиа (фото/стикеры/видео/webm)
    ├── backups/daily/              — daily substrate backup (cron 04:00 UTC)
    ├── searxng/
    │   └── settings.yml            — runtime SearXNG config (с auto-generated secret_key)
    └── selfmod_backups/            — pre-state files captured before selfmod.apply
```

## 5. Управление сервисами

### Systemd (sonya core, admin panel)

```bash
# Статус
sudo systemctl status sonya
sudo systemctl status sonya-admin

# Перезапуск
sudo systemctl restart sonya sonya-admin

# Логи (live)
sudo journalctl -u sonya -f
sudo journalctl -u sonya-admin -f

# Остановить
sudo systemctl stop sonya
```

### Docker (SearXNG)

```bash
# Статус
docker ps | grep sonya-searxng

# Перезапуск
docker restart sonya-searxng

# Логи
docker logs sonya-searxng -f

# Остановить
docker stop sonya-searxng

# Полный re-setup (если что-то сломалось)
bash ~/Sonya/deploy/searxng/setup.sh
```

## 6. Обновление кода

```bash
# С локальной машины
ssh jester-sonya@34.38.255.149 "bash ~/Sonya/deploy/update.sh"
```

`update.sh` делает: сохраняет diverged-коммиты Сони (если автопуш не прошёл) → `git fetch + reset --hard origin/develop` → `pip install` runtime deps (fastembed/numpy/imagehash) → `systemctl restart sonya sonya-admin`. На старте ядра запускается идемпотентная миграция knowledge (legacy repo-папки → `~/.sonya/knowledge/`, лог `knowledge_migrated`).

**SearXNG не трогается** — у него отдельный setup.sh. Запускать только если меняется его конфиг.

## 7. Self-hosted SearXNG

### Назначение

Meta-search engine на VPS. Агрегирует результаты с Google, Bing, DDG, Brave, Qwant, Wikipedia, GitHub, StackOverflow, arxiv. JSON API на `127.0.0.1:8888/search?q=X&format=json`.

### Зачем нужен

DDG и Google блокируют наш VPS IP (302 redirect к captcha). SearXNG агрегирует с разных источников через свой контейнер — мы получаем чистый JSON без блокировок и captcha. Plus полная независимость — никаких API ключей и rate limits.

### Как Соня его использует

В `.env` стоит:
```
SONYA_SEARXNG_URL=http://127.0.0.1:8888
```

`web.search` пробует endpoints в порядке:
1. **Свой SearXNG** (через env-var) — primary
2. 8 публичных SearXNG instances в случайном порядке (если свой упал)
3. DDG HTML scrape (последний шанс)
4. Google HTML scrape (часто блокируется)

См. `src/sonya/tools/web_tool.py`.

### Первичный setup

```bash
bash ~/Sonya/deploy/searxng/setup.sh
```

Этот скрипт:
- Создаёт `~/.sonya/searxng/settings.yml` с auto-generated secret_key (если ещё нет)
- Pull docker image `searxng/searxng:latest`
- Запускает контейнер с `--restart unless-stopped`, bound на `127.0.0.1:8888`
- Health check + JSON API test

Idempotent — можно гонять повторно.

### Если SearXNG лежит

Соня автоматически фолбэчится на публичные инстансы. Чтобы починить:
```bash
docker restart sonya-searxng
docker logs sonya-searxng | tail -30
```

Если не помогло — `bash ~/Sonya/deploy/searxng/setup.sh` пересоздаёт контейнер.

## 8. Backup substrate

Автоматический ежедневный backup через cron в `~/.sonya/backups/daily/`. Ручной:

```bash
sqlite3 ~/.sonya/sonya_substrate.db ".backup ~/.sonya/manual_$(date +%Y%m%d).db"
```

Через `cp` опасно — substrate в WAL mode, файл может быть corrupt.

Cron entry: проверь `crontab -l`.

## 9. .env на сервере

```bash
# Telegram (Telethon)
SONYA_TG_API_ID=...
SONYA_TG_API_HASH=...
SONYA_TG_SESSION_PATH=./tg.session
SONYA_PRIMARY_USER_TG_ID=5785127604

# Admin panel
SONYA_ADMIN_PASSWORD=...

# Logging
SONYA_LOG_LEVEL=INFO

# YOLO: shell.run / pip.install без approval Ивана
SONYA_YOLO_MODE=1

# Search backend
SONYA_SEARXNG_URL=http://127.0.0.1:8888
```

LLM-провайдер (Fireworks/OpenRouter), default_model и API keys хранятся **в substrate** (`provider_keys` + `provider_settings` tables), не в .env. Редактируется через admin panel → Providers.

## 10. Firewall правила (GCP)

| Rule | Port | Source | Описание |
|------|------|--------|----------|
| default-allow-http | 80 | 0.0.0.0/0 | HTTP (не используется) |
| allow-sonya-admin | 8877 | 0.0.0.0/0 | Admin panel |

SearXNG (8888) **не открыт** наружу — только localhost. Доступ только изнутри сервера через `127.0.0.1:8888`.

## 11. Деплой с локальной машины (Windows + PowerShell)

```powershell
# Commit + push
git add -A; git commit -m "..."; git push origin develop

# Pull на сервере + restart
ssh jester-sonya@34.38.255.149 "bash ~/Sonya/deploy/update.sh"
```

## 12. Что НЕ менять руками на сервере

- `~/.sonya/sonya_substrate.db` — substrate Сони, её память и identity
- `~/Sonya/tg.session` — авторизация Telegram (потеряешь — Соня выйдет из аккаунта)
- ключи провайдеров в `provider_keys` table — правь через admin Providers tab
- `~/.sonya/searxng/settings.yml` после auto-generate (там реальный secret_key)
- `~/.sonya/knowledge/` — её факт-база. Читать можно, но писать/править руками не нужно: Соня сама управляет через `knowledge.*` tools. Editing вручную допустимо только для disaster-recovery (восстановление потерянного знания).

## 13. Что мониторить

| Команда | Что смотреть |
|---------|--------------|
| `free -h` | RAM (norm: ~4-5 GB free; embedder ест ~150 MB, SearXNG ~200 MB) |
| `df -h /` | disk (norm: ~30+ GB free) |
| `docker ps` | sonya-searxng `Up` |
| `systemctl is-active sonya` | active |
| `journalctl -u sonya -p warning -n 50` | warnings/errors последнего часа |
| `~/.cache/fastembed/` | embedding model (~80 MB, скачивается один раз) |

## 14. Известные quirks

- `channel_stop_failed: attempt to write a readonly database` при shutdown sonya — это Telethon's session SQLite, которая закрывается раньше его keep-alive task. Не функциональная проблема, log warning только при рестарте.
- WAL files (`*.db-wal`, `*.db-shm`) растут между checkpoints — это нормально, sqlite сам зачищает.
- SearXNG первый запрос после старта контейнера может занять 5-10 сек (engine warmup).

## 15. Disaster recovery

### Сервер целиком умер
1. Создать новый GCE инстанс (Debian 12, e2-medium минимум)
2. Установить deps: `apt install python3.11 python3.11-venv git docker.io sqlite3`
3. `git clone https://github.com/VernaculusF/Sonya ~/Sonya && cd ~/Sonya && python3.11 -m venv .venv`
4. `~/Sonya/.venv/bin/pip install -e . -e packages/tg-userbot fastembed numpy imagehash`
5. Восстановить `~/.sonya/sonya_substrate.db` из последнего daily backup
6. Восстановить `~/Sonya/.env` (есть локальная копия?) и `tg.session`
7. `bash ~/Sonya/deploy/searxng/setup.sh`
8. Скопировать systemd units: `sudo cp deploy/systemd/*.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable sonya sonya-admin && sudo systemctl start sonya sonya-admin`

### Substrate corrupt
1. `sudo systemctl stop sonya`
2. Восстановить из `~/.sonya/backups/daily/<latest>.db`
3. `sudo systemctl start sonya`

### Knowledge база потеряна
Её факт-база (`~/.sonya/knowledge/`) бэкапится отдельным tarball'ом рядом с substrate:
1. `cd ~/.sonya`
2. `tar -xzf ~/.sonya/backups/daily/knowledge_<latest>.tar.gz`
3. Перезапуск не нужен — `knowledge.*` tools читают директорию на лету.

### Telegram session invalid
1. Удалить `~/Sonya/tg.session` и `tg.session-journal`
2. Запустить интерактивно: `cd ~/Sonya && .venv/bin/python -m sonya` → введёт код подтверждения через TG SMS
3. После авторизации `Ctrl+C`, `sudo systemctl restart sonya`
