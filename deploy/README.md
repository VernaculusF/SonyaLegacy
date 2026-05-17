# Sonya — Deployment

## Реальный layout на VPS

```
/home/jester-sonya/
├── Sonya/                    # git checkout (this repo)
│   ├── .venv/                # virtualenv
│   ├── .env                  # secrets and config (mode 600)
│   ├── tg.session            # Telegram userbot auth (NOT in git)
│   └── deploy/
│       ├── systemd/
│       │   ├── sonya.service        # core runtime
│       │   └── sonya-admin.service  # web admin panel
│       └── update.sh                # safe pull + restart
└── .sonya/
    ├── sonya_substrate.db    # subject substrate (memory, identity, state)
    └── health.json           # health-ping
```

## Установка systemd-юнитов (один раз)

```bash
sudo cp /home/jester-sonya/Sonya/deploy/systemd/sonya.service /etc/systemd/system/
sudo cp /home/jester-sonya/Sonya/deploy/systemd/sonya-admin.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable sonya-admin    # admin запускается всегда
# core запускается только когда нужно (через admin panel)
sudo systemctl start sonya-admin
```

После этого admin панель будет доступна на `http://VPS_IP:8877` (если firewall открыт).

Запуск/остановка ядра — через admin панель (вкладка `⚙️ Core`).

## Обновление кода

```bash
ssh jester-sonya@VPS_IP
bash ~/Sonya/deploy/update.sh
```

Скрипт:
- pull latest develop
- проверит права на substrate
- удалит stale lock файлы
- перезапустит systemd-сервисы (или nohup-fallback если systemd не настроен)

## Запуск без systemd (fallback)

Если systemd ещё не настроен — admin запускается вручную:

```bash
cd ~/Sonya
PYTHONPATH=src:packages/tg-userbot/src:packages/tg-bridge/src \
    nohup .venv/bin/python -m sonya.admin > /tmp/sonya-admin.log 2>&1 &
```

Затем core можно запустить через admin UI.

## Локальная разработка

```bash
python3.11 -m venv .venv
. .venv/bin/activate           # PowerShell: . .venv/Scripts/Activate.ps1
pip install -e .

# В одном терминале — admin (по умолчанию 127.0.0.1:8877):
python -m sonya.admin

# В другом — core напрямую (для отладки):
python -m sonya
```

## Backup substrate

```bash
sudo systemctl stop sonya
cp ~/.sonya/sonya_substrate.db ~/.sonya/backup-$(date +%F).db
sudo systemctl start sonya
```

Hot backup (без остановки) — через `sqlite3 .backup`:

```bash
sqlite3 ~/.sonya/sonya_substrate.db ".backup ~/.sonya/backup-$(date +%F).db"
```

## Multi-process safety

Один core process — write-master substrate. Запуск второго инстанса против того же файла = exit code 3 + лог `write-master contention`.

Admin панель открывает substrate отдельно для чтения (см. KNOWN_ISSUES C-5 — пока есть гонка при запущенном core).

## Stopping cleanly

`systemctl stop sonya` → SIGTERM → `subject.lifecycle.stopping` → `subject.lifecycle.stopped` → exit в пределах `TimeoutStopSec=15`.

## Что НЕ хранится в `.env`

- subject identity, principals, relation anchors — они в substrate
- conversation history — substrate (episodic memory)
- session_secret админки — генерится в памяти процесса при старте
