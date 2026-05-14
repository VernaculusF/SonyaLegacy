# Sonya — Deployment notes

This directory holds operational artefacts for running Sonya as a service.

## Layout assumed on a VPS

```
/opt/sonya/
  .git/                   # checkout of this repo
  .venv/                  # virtualenv
  .env                    # secrets and config (mode 600)
  var/
    sonya_substrate.db    # substrate
    health.json           # health-ping
```

## Local quick start

```bash
python3.11 -m venv .venv
. .venv/bin/activate           # PowerShell: . .venv/Scripts/Activate.ps1
pip install -e .
SONYA_SUBSTRATE_PATH=$PWD/var/sonya_substrate.db \
SONYA_HEALTH_PATH=$PWD/var/health.json \
SONYA_LOG_LEVEL=INFO \
python -m sonya
```

`Ctrl+C` triggers a graceful shutdown (lifecycle.stopping → continuity event → lifecycle.stopped).

## VPS install

```bash
sudo install -d -o sonya -g sonya /opt/sonya
sudo -u sonya git clone <repo-url> /opt/sonya
cd /opt/sonya
sudo -u sonya python3.11 -m venv .venv
sudo -u sonya .venv/bin/pip install -e .
sudo install -m 600 -o sonya -g sonya /dev/stdin /opt/sonya/.env <<'EOF'
SONYA_SUBSTRATE_PATH=/opt/sonya/var/sonya_substrate.db
SONYA_HEALTH_PATH=/opt/sonya/var/health.json
SONYA_LOG_LEVEL=INFO
EOF
sudo cp deploy/systemd/sonya.service /etc/systemd/system/sonya.service
sudo systemctl daemon-reload
sudo systemctl enable --now sonya
sudo systemctl status sonya
journalctl -u sonya -f
```

## What is and is not in `.env`

In `.env`:

- `SONYA_SUBSTRATE_PATH` — path to substrate SQLite file.
- `SONYA_HEALTH_PATH` — path to health-ping JSON.
- `SONYA_LOG_LEVEL` — `DEBUG` / `INFO` / `WARNING` / `ERROR`.
- Future provider/channel secrets land here in later phases.

Not in `.env`:

- subject identity, principals, relation anchors — these live inside the substrate, not the env.

## Backup

Substrate is one SQLite file; copy it while the process is stopped, or use `sqlite3 .backup` against a live process.

```bash
sudo systemctl stop sonya
sudo -u sonya cp /opt/sonya/var/sonya_substrate.db /opt/sonya/var/backup-$(date +%F).db
sudo systemctl start sonya
```

## Multi-process safety

A single sonya process is the write-master at any time. Starting a second instance against the same substrate refuses with exit code 3 and a write-master contention log entry.

## Stopping cleanly

`systemctl stop sonya` sends `SIGTERM`. Sonya emits `subject.lifecycle.stopping`, appends `subject.lifecycle.stopped` to continuity, and exits within `TimeoutStopSec`.
