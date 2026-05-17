#!/bin/bash
# Sonya substrate backup — daily snapshot with rotation.
# Run from cron: 0 4 * * * bash /home/jester-sonya/Sonya/deploy/backup.sh
#
# Strategy: SQLite .backup API (atomic, online — no need to stop the core).
# Stores in ~/.sonya/backups/, keeps last 14 daily + last 8 weekly snapshots.

set -e

SUBSTRATE="$HOME/.sonya/sonya_substrate.db"
BACKUP_DIR="$HOME/.sonya/backups"
DATE=$(date -u +%Y-%m-%d)
WEEKDAY=$(date -u +%u)  # 1..7 (Mon..Sun)

mkdir -p "$BACKUP_DIR/daily" "$BACKUP_DIR/weekly"

if [ ! -f "$SUBSTRATE" ]; then
    echo "[backup] substrate not found: $SUBSTRATE" >&2
    exit 1
fi

DAILY="$BACKUP_DIR/daily/sonya_$DATE.db"

# Use sqlite3 .backup which is atomic and works while DB is in WAL mode.
# Falls back to plain copy if sqlite3 is missing.
if command -v sqlite3 >/dev/null; then
    sqlite3 "$SUBSTRATE" ".backup '$DAILY'"
else
    cp -p "$SUBSTRATE" "$DAILY"
fi

gzip -f "$DAILY"
echo "[backup] daily: ${DAILY}.gz"

# Sunday → also copy to weekly
if [ "$WEEKDAY" = "7" ]; then
    cp "$DAILY.gz" "$BACKUP_DIR/weekly/sonya_$DATE.db.gz"
    echo "[backup] weekly: $BACKUP_DIR/weekly/sonya_$DATE.db.gz"
fi

# Rotation: keep last 14 daily, last 8 weekly
ls -1t "$BACKUP_DIR/daily"/*.db.gz 2>/dev/null | tail -n +15 | xargs -r rm -v
ls -1t "$BACKUP_DIR/weekly"/*.db.gz 2>/dev/null | tail -n +9 | xargs -r rm -v

echo "[backup] done"
