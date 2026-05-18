# VPS Operations — Sonya Hosting

**Status:** Active
**Type:** Operations
**Last updated:** 2026-05-18

## Где хостится

- **Provider:** Google Cloud Platform (GCE)
- **Instance:** `instance-20260516-063101`
- **Zone:** `europe-west1-b` (Belgium)
- **Machine:** e2-custom (4 vCPU / 8 GB RAM)
- **OS:** Debian 12
- **External IP:** `34.38.255.149`
- **Disk:** 50 GB Balanced Persistent Disk
- **Budget:** $300 free credits (expires ~August 2026)

## Что там работает

| Service | Port | Описание |
|---------|------|----------|
| sonya.service | — | Ядро: substrate + thinking loop + telegram userbot + embedding indexer |
| sonya-admin.service | 8877 | Web-панель (пароль в .env) |

OmniRoute удалён. LLM-вызовы идут напрямую через `sonya.providers.llm_provider` с собственной key pool в substrate.

## Как подключиться

```bash
ssh jester-sonya@34.38.255.149
```

## Пути на сервере

```
/home/jester-sonya/
├── Sonya/                  — проект (git clone)
│   ├── src/sonya/          — ядро
│   ├── packages/tg-userbot — Telethon обёртка
│   ├── .env                — конфиг (TG api id/hash, admin password)
│   ├── tg.session          — Telegram userbot session
│   └── .venv/              — Python virtual environment
│
└── .sonya/
    ├── sonya_substrate.db  — substrate (substrate v13)
    ├── media/              — скачанные TG медиа (фото/стикеры)
    ├── backups/daily/      — daily substrate backup (cron 04:00 UTC)
    └── omniroute_keys_backup.json — резерв старых ключей
```

## Управление сервисами

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

## Обновление кода

```bash
# С локальной машины
ssh jester-sonya@34.38.255.149 "bash ~/Sonya/deploy/update.sh"
```

`update.sh` делает: git pull → pip install runtime deps (fastembed/numpy на случай первичной установки) → systemctl restart.

## Backup substrate

Автоматический ежедневный backup через cron в `~/.sonya/backups/daily/`. Ручной:

```bash
sqlite3 ~/.sonya/sonya_substrate.db ".backup ~/.sonya/manual_$(date +%Y%m%d).db"
```

Через `cp` опасно — substrate в WAL mode, файл может быть corrupt.

## .env на сервере

```
SONYA_TG_API_ID=...
SONYA_TG_API_HASH=...
SONYA_TG_SESSION_PATH=./tg.session
SONYA_ADMIN_PASSWORD=...
SONYA_PRIMARY_USER_TG_ID=5785127604
SONYA_LOG_LEVEL=INFO
SONYA_YOLO_MODE=1   # shell.run / pip.install без approval
```

LLM-провайдер (Fireworks) и default_model хранятся **в substrate** (`provider_settings` table), не в .env. Редактируется через admin panel → Providers.

## Firewall правила

| Rule | Port | Source | Описание |
|------|------|--------|----------|
| default-allow-http | 80 | 0.0.0.0/0 | HTTP (не используется) |
| allow-sonya-admin | 8877 | 0.0.0.0/0 | Admin panel |

## Деплой с локальной машины

```powershell
# Commit + push
git add -A; git commit -m "..."; git push origin develop

# Pull на сервере + restart
ssh jester-sonya@34.38.255.149 "bash ~/Sonya/deploy/update.sh"
```

## Что НЕ менять руками на сервере

- `sonya_substrate.db` — substrate Сони, её память и identity
- `tg.session` — авторизация Telegram (потеряешь — Соня выйдет из аккаунта)
- ключи провайдеров в `provider_keys` table (правь через admin Providers tab)

## Что мониторить

- `free -h` — RAM (norm: ~5.5+ GB free; embedder при первой загрузке ест ~120-150 MB)
- `df -h /` — disk (norm: ~40+ GB free)
- `~/.cache/fastembed/` — модель эмбеддинга (~80 MB), скачивается один раз
