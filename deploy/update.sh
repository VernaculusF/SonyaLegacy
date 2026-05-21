#!/bin/bash
# Sonya VPS update script — pulls latest code, restarts services cleanly.
# Run as: bash ~/Sonya/deploy/update.sh

set -e

PROJECT_DIR="$HOME/Sonya"
SUBSTRATE_DIR="$HOME/.sonya"

cd "$PROJECT_DIR"

echo "=> Fetching latest code..."
git fetch origin
git reset --hard origin/develop

echo "=> Ensuring substrate directory exists with correct permissions..."
mkdir -p "$SUBSTRATE_DIR"
chmod 755 "$SUBSTRATE_DIR"
# Ensure substrate file is writable by current user (in case git reset touched it)
if [ -f "$SUBSTRATE_DIR/sonya_substrate.db" ]; then
    chmod 644 "$SUBSTRATE_DIR/sonya_substrate.db"
fi

echo "=> Cleaning stale lock files..."
rm -f "$SUBSTRATE_DIR"/*.lock

echo "=> Ensuring runtime dependencies..."
# fastembed + numpy power memory.recall (semantic search over episodic memory).
# Idempotent — pip skips if already at the requested version.
"$PROJECT_DIR/.venv/bin/pip" install --quiet --upgrade \
    "fastembed>=0.4" "numpy>=1.26" "imagehash>=4.3" 2>&1 | grep -v "already satisfied" || true

echo "=> Restarting services..."
if systemctl --user list-units 2>/dev/null | grep -q sonya; then
    systemctl --user restart sonya sonya-admin 2>/dev/null || true
elif [ -f /etc/systemd/system/sonya.service ] && command -v sudo >/dev/null && sudo -n true 2>/dev/null; then
    sudo systemctl restart sonya sonya-admin
else
    echo "!! systemd not configured — falling back to nohup"
    pkill -9 -f 'python.*sonya' 2>/dev/null || true
    sleep 2
    PYTHONPATH="$PROJECT_DIR/src:$PROJECT_DIR/packages/tg-userbot/src" \
        nohup "$PROJECT_DIR/.venv/bin/python" -m sonya.admin \
        > /tmp/sonya-admin.log 2>&1 &
    echo "Admin started (nohup). Logs: /tmp/sonya-admin.log"
    echo "Core not started — use admin panel to start it."
fi

echo "=> Done."
