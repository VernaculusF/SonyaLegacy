#!/usr/bin/env bash
set -eo pipefail

# SONYA ENCRYPTED BACKUP SCRIPT
# This script performs a safe sqlite backup, encrypts it, and uploads it to an off-host location.
# Requires: sqlite3, gpg, s3cmd (or scp)
# Usage: ./backup_encrypted.sh

DB_PATH="${SONYA_DB_PATH:-/home/jester-sonya/.sonya/sonya_substrate.db}"
BACKUP_DIR="/tmp/sonya_backup"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/sonya_backup_${TIMESTAMP}.tar.gz"
ENCRYPTED_FILE="${BACKUP_FILE}.gpg"

# Destination: replace with actual S3 bucket or SSH destination
REMOTE_DEST="s3://sonya-backups/db/"

echo "[+] Starting encrypted backup of Sonya substrate and session..."

mkdir -p "$BACKUP_DIR"

if [ ! -f "$DB_PATH" ]; then
    echo "[-] Database not found at $DB_PATH"
    exit 1
fi

echo "[+] Creating safe SQLite snapshot via Python..."
# SQLite safe online backup to avoid locking issues
python3 -c "import sqlite3; src = sqlite3.connect('${DB_PATH}'); dst = sqlite3.connect('${BACKUP_DIR}/sonya_substrate.db'); src.backup(dst); dst.close(); src.close()"

echo "[+] Archiving substrate and Telegram session..."
# Assuming tg.session is stored in the standard location (configurable in .env)
TG_SESSION_SRC="${SONYA_TG_SESSION_SRC:-/home/jester-sonya/.sonya/tg.session}"
cp ${TG_SESSION_SRC}* "${BACKUP_DIR}/" 2>/dev/null || echo "[-] No tg.session found to backup."
tar -czf "$BACKUP_FILE" -C "$BACKUP_DIR" sonya_substrate.db tg.session tg.session-journal 2>/dev/null || tar -czf "$BACKUP_FILE" -C "$BACKUP_DIR" sonya_substrate.db

echo "[+] Encrypting backup..."
# Symmetrically encrypt using the passphrase from the environment variable SONYA_BACKUP_PASS
if [ -z "$SONYA_BACKUP_PASS" ]; then
    echo "[-] SONYA_BACKUP_PASS environment variable is not set. Cannot encrypt."
    rm -f "$BACKUP_FILE"
    exit 1
fi

gpg --batch --yes --passphrase "$SONYA_BACKUP_PASS" --symmetric --cipher-algo AES256 -o "$ENCRYPTED_FILE" "$BACKUP_FILE"

echo "[+] Uploading to off-host storage ($REMOTE_DEST)..."
# Here we simulate an S3 upload. Replace with aws s3 cp or scp as configured on the VPS.
if command -v s3cmd &> /dev/null; then
    s3cmd put "$ENCRYPTED_FILE" "$REMOTE_DEST"
else
    echo "[!] s3cmd not found. Skipping remote upload. File is saved locally at: $ENCRYPTED_FILE"
    # Fallback simulation
    mkdir -p /home/jester-sonya/.sonya/mock_remote_backup/
    cp "$ENCRYPTED_FILE" /home/jester-sonya/.sonya/mock_remote_backup/
fi

echo "[+] Cleaning up plaintext backup..."
rm -f "$BACKUP_FILE"

echo "[+] Backup complete: $ENCRYPTED_FILE"
