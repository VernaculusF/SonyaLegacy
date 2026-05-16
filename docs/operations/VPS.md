# VPS Operations — Sonya Hosting

**Status:** Active
**Type:** Operations
**Last updated:** 2026-05-16

## Где хостится

- **Provider:** Google Cloud Platform (GCE)
- **Instance:** `instance-20260516-063101`
- **Zone:** `europe-west1-b` (Belgium)
- **Machine:** e2-custom (4 vCPU / 8 GB RAM)
- **OS:** Debian 12
- **External IP:** `34.38.255.149`
- **Disk:** 20 GB Balanced Persistent Disk
- **Budget:** $300 free credits (expires ~August 2026)

## Что там работает

| Service | Port | Описание |
|---------|------|----------|
| sonya.service | — | Ядро: substrate + thinking loop + telegram userbot |
| sonya-admin.service | 8877 | Web-панель (пароль: в .env) |
| OmniRoute (Docker) | 20128 | LLM proxy с 12 fireworks ключами |

## Как подключиться

```bash
# С локальной машины (ключ уже настроен):
ssh jester-sonya@34.38.255.149
```

## Пути на сервере

```
/home/jester-sonya/
├── Sonya/              — проект (git clone)
│   ├── src/sonya/      — ядро
│   ├── packages/       — tg-bridge, tg-userbot
│   ├── .env            — конфиг (ключи, модель, пароли)
│   ├── tg.session      — Telegram userbot session
│   └── .venv/          — Python virtual environment
│
├── omniroute_data/     — данные OmniRoute
│   ├── storage.sqlite  — ключи и настройки провайдеров
│   └── server.env      — JWT/encryption secrets
│
└── .sonya/
    └── sonya_substrate.db  — substrate (основная БД Сони)
```

## Управление сервисами

```bash
# Статус
sudo systemctl status sonya
sudo systemctl status sonya-admin

# Перезапуск
sudo systemctl restart sonya
sudo systemctl restart sonya-admin

# Логи (live)
sudo journalctl -u sonya -f
sudo journalctl -u sonya-admin -f

# Остановить
sudo systemctl stop sonya

# OmniRoute
sudo docker logs omniroute --tail 20
sudo docker restart omniroute
```

## Обновление кода

```bash
cd ~/Sonya
git pull origin develop
sudo systemctl restart sonya sonya-admin
```

## Backup substrate

```bash
cp ~/.sonya/sonya_substrate.db ~/.sonya/backup_$(date +%Y%m%d).db
```

## .env на сервере

```
SONYA_LLM_API_BASE=http://127.0.0.1:20128/v1
SONYA_LLM_MODEL=fireworks/accounts/fireworks/models/minimax-m2p7
SONYA_OPENROUTER_API_KEY=sk-...
SONYA_TG_API_ID=2040
SONYA_TG_API_HASH=b18441a1ff607e10a989891a5462e627
SONYA_TG_SESSION_PATH=./tg.session
SONYA_ADMIN_PASSWORD=1990
SONYA_LOG_LEVEL=INFO
```

## Firewall правила

| Rule | Port | Source | Описание |
|------|------|--------|----------|
| default-allow-http | 80 | 0.0.0.0/0 | HTTP (не используется) |
| allow-sonya-admin | 8877 | 0.0.0.0/0 | Admin panel |

## Как деплоить с локальной машины

```powershell
# 1. Commit + push
git add -A; git commit -m "..."; git push origin develop

# 2. Pull на сервере + restart
ssh jester-sonya@34.38.255.149 "cd ~/Sonya && git pull origin develop && sudo systemctl restart sonya sonya-admin"
```

## Что НЕ менять руками на сервере

- `sonya_substrate.db` — это substrate Сони, её память и identity
- `tg.session` — авторизация Telegram
- `omniroute_data/storage.sqlite` — ключи провайдеров
