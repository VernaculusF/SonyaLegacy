#!/usr/bin/env bash
set -eo pipefail

# SONYA RESTORE DRILL SCRIPT
# This script fetches the latest encrypted backup, decrypts it, and verifies its SQLite integrity.
# It proves RPO/RTO capability.
# Usage: ./restore_drill.sh <path_or_url_to_backup>

if [ -z "$1" ]; then
    echo "Usage: $0 <path_to_encrypted_backup_file>"
    exit 1
fi

ENCRYPTED_FILE="$1"
RESTORE_DIR="/tmp/sonya_restore_drill"
DECRYPTED_FILE="${RESTORE_DIR}/sonya_backup.tar.gz"

if [ -z "$SONYA_BACKUP_PASS" ]; then
    echo "[-] SONYA_BACKUP_PASS environment variable is not set. Cannot decrypt."
    exit 1
fi

mkdir -p "$RESTORE_DIR"

echo "[+] Decrypting $ENCRYPTED_FILE..."
gpg --batch --yes --passphrase "$SONYA_BACKUP_PASS" --decrypt -o "$DECRYPTED_FILE" "$ENCRYPTED_FILE"

echo "[+] Extracting backup..."
tar -xzf "$DECRYPTED_FILE" -C "$RESTORE_DIR"

echo "[+] Verifying SQLite database integrity via Python..."
INTEGRITY=$(python3 -c "import sqlite3; c=sqlite3.connect('${RESTORE_DIR}/sonya_substrate.db'); res=c.execute('PRAGMA integrity_check;').fetchone()[0]; print(res); c.close()")

if [ "$INTEGRITY" == "ok" ]; then
    echo "[+] Restore drill SUCCESSFUL. Database integrity is OK."
else
    echo "[-] Restore drill FAILED. Integrity check returned: $INTEGRITY"
    exit 1
fi

echo "[+] Clean up..."
rm -f "$DECRYPTED_FILE"
echo "[+] Drill complete."
