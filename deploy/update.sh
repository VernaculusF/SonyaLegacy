#!/bin/bash
# Sonya VPS update script — pulls latest code, restarts services cleanly.
# Run as: bash ~/Sonya/deploy/update.sh

set -e

PROJECT_DIR="$HOME/Sonya"
SUBSTRATE_DIR="$HOME/.sonya"

cd "$PROJECT_DIR"

echo "=> Checking for uncommitted local changes..."
# selfmod.apply() commits + pushes directly to current branch (develop) on
# success. If working tree is dirty here, something interrupted that flow
# (push failed mid-way, manual edit, etc.). Stash to a backup branch so
# git reset --hard doesn't silently nuke the work.
if ! git diff --quiet || ! git diff --cached --quiet; then
    BACKUP_BRANCH="sonya-selfmod/local-backup-$(date +%Y%m%d-%H%M%S)"
    echo "!! Working tree is dirty. Saving to branch: $BACKUP_BRANCH"
    git checkout -B "$BACKUP_BRANCH"
    git add -A
    git -c user.name="Sonya" -c user.email="sonya@local" commit -m "selfmod: emergency backup before deploy" || true
    git push --set-upstream origin "$BACKUP_BRANCH" 2>&1 | grep -v "^$" || true
    git checkout develop 2>/dev/null || git checkout -B develop origin/develop
fi

echo "=> Fetching latest code..."
git fetch origin
# Soft-reset semantics: if local develop has commits ahead of origin (Sonya
# pushed selfmod here that hasn't been fetched on the dev box yet), we want
# to keep them. Use merge --ff-only first; fall back to hard reset if
# branches truly diverged.
if ! git merge --ff-only origin/develop 2>/dev/null; then
    echo "!! local develop diverged from origin/develop — hard reset"
    git reset --hard origin/develop
fi

echo "=> Ensuring substrate directory exists with correct permissions..."
mkdir -p "$SUBSTRATE_DIR"
chmod 755 "$SUBSTRATE_DIR"
# Ensure substrate file is writable by current user (in case git reset touched it)
if [ -f "$SUBSTRATE_DIR/sonya_substrate.db" ]; then
    chmod 644 "$SUBSTRATE_DIR/sonya_substrate.db"
fi

echo "=> Cleaning stale lock files..."
rm -f "$SUBSTRATE_DIR"/*.lock

echo "=> Checking sonya-omniroute container..."
# kr/* models (Sonnet 4.5 / Haiku 4.5) reach Kiro via this local container.
# It has restart=unless-stopped, so normally it self-recovers. But on some
# host upgrades / kernel issues docker stops bringing it back. Check + nudge.
if command -v docker >/dev/null 2>&1; then
    if docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^sonya-omniroute$'; then
        echo "   sonya-omniroute: running"
    elif docker ps -a --format '{{.Names}}' 2>/dev/null | grep -q '^sonya-omniroute$'; then
        echo "   sonya-omniroute: starting (was stopped)"
        docker start sonya-omniroute >/dev/null 2>&1 || true
    else
        echo "   sonya-omniroute: not present (kr/* fallback unavailable until reseeded)"
    fi
fi

echo "=> Ensuring runtime dependencies..."
# fastembed + numpy power memory.recall (semantic search over episodic memory).
# pytest required for selfmod Layer 2 sandbox (runs project tests against modified code).
# Idempotent — pip skips if already at the requested version.
"$PROJECT_DIR/.venv/bin/pip" install --quiet --upgrade \
    "fastembed>=0.4" "numpy>=1.26" "imagehash>=4.3" \
    "pytest>=8.0" "pytest-timeout>=2.0" "pytest-asyncio>=0.23" \
    2>&1 | grep -v "already satisfied" || true

echo "=> Restarting services..."
# Helper: verify Sonya core + admin are alive (or absent if expected) and
# port 8877 is bound by the new admin process. Returns 0 if healthy.
verify_sonya_running() {
    local core_pid admin_pid
    core_pid=$(pgrep -f '/home/jester-sonya/Sonya/.venv/bin/python -m sonya$' || true)
    admin_pid=$(pgrep -f '/home/jester-sonya/Sonya/.venv/bin/python -m sonya.admin' || true)
    if [ -z "$core_pid" ] || [ -z "$admin_pid" ]; then
        echo "!! verify failed: core_pid=$core_pid admin_pid=$admin_pid"
        return 1
    fi
    echo "   core=$core_pid admin=$admin_pid"
    return 0
}

# Helper: kill any sonya core/admin using full venv path so we don't miss
# them and don't accidentally hit unrelated python processes.
kill_old_sonya() {
    local pids
    pids=$(pgrep -f '/home/jester-sonya/Sonya/.venv/bin/python -m sonya' || true)
    if [ -n "$pids" ]; then
        echo "   killing old PIDs: $pids"
        kill -TERM $pids 2>/dev/null || true
        sleep 2
        # Anything still alive gets -9
        pids=$(pgrep -f '/home/jester-sonya/Sonya/.venv/bin/python -m sonya' || true)
        if [ -n "$pids" ]; then
            echo "   force-killing: $pids"
            kill -9 $pids 2>/dev/null || true
            sleep 1
        fi
    fi
    # Free up admin port if anything is still squatting on it.
    if command -v lsof >/dev/null && lsof -ti:8877 >/dev/null 2>&1; then
        local port_pids
        port_pids=$(lsof -ti:8877 || true)
        if [ -n "$port_pids" ]; then
            echo "   freeing port 8877 from PIDs: $port_pids"
            kill -9 $port_pids 2>/dev/null || true
            sleep 1
        fi
    fi
}

if systemctl --user list-units 2>/dev/null | grep -q sonya; then
    systemctl --user restart sonya sonya-admin 2>/dev/null || true
elif [ -f /etc/systemd/system/sonya.service ] && command -v sudo >/dev/null && sudo -n true 2>/dev/null; then
    sudo systemctl restart sonya sonya-admin
else
    echo "!! systemd not configured — falling back to nohup"
    kill_old_sonya
    PYTHONPATH="$PROJECT_DIR/src:$PROJECT_DIR/packages/tg-userbot/src" \
        nohup "$PROJECT_DIR/.venv/bin/python" -m sonya.admin \
        > /tmp/sonya-admin.log 2>&1 &
    echo "Admin spawned (nohup). Logs: /tmp/sonya-admin.log"
    PYTHONPATH="$PROJECT_DIR/src:$PROJECT_DIR/packages/tg-userbot/src" \
        nohup "$PROJECT_DIR/.venv/bin/python" -m sonya \
        > /tmp/sonya.log 2>&1 &
    echo "Core spawned (nohup). Logs: /tmp/sonya.log"
    sleep 3
    if ! verify_sonya_running; then
        echo "!! restart verification failed — admin/core didn't come up."
        echo "   admin log tail:" && tail -n 20 /tmp/sonya-admin.log 2>/dev/null
        echo "   core  log tail:" && tail -n 20 /tmp/sonya.log 2>/dev/null
        exit 1
    fi
fi

echo "=> Done."
