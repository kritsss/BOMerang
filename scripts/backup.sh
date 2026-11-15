#!/usr/bin/env bash
# Copies the whole BOMerang data volume (SQLite DB + uploads + run results) to ~/bomerang-backups,
# keeping the last 7. The DB itself is copied with SQLite's online backup, so it is safe while the app runs.
# Nightly at 03:17:  (crontab -l 2>/dev/null; echo "17 3 * * * $HOME/BOMerang/scripts/backup.sh >> $HOME/bomerang-backups/backup.log 2>&1") | crontab -
set -euo pipefail
cd "$(dirname "$0")/.."
DEST="$HOME/bomerang-backups"; mkdir -p "$DEST"
STAMP=$(date +%Y%m%d-%H%M%S)
DC="docker compose -f docker-compose.prod.yml"
command -v docker >/dev/null && docker info >/dev/null 2>&1 || DC="sudo $DC"

$DC exec -T api python - <<'PY'
import sqlite3, os
src = os.path.join(os.environ.get("BOMERANG_DATA_DIR", "/data"), "bomerang.db")
if os.path.exists(src):
    os.makedirs("/tmp/bk", exist_ok=True)
    s, d = sqlite3.connect(src), sqlite3.connect("/tmp/bk/bomerang.db")
    s.backup(d); d.close(); s.close()
PY
$DC exec -T api sh -c 'cd /data && tar --anchored --exclude=./bomerang.db --exclude=./bomerang.db-wal --exclude=./bomerang.db-shm --exclude=./bomerang.db-journal -czf - . -C /tmp/bk bomerang.db 2>/dev/null' > "$DEST/bomerang-$STAMP.tar.gz"
ls -1t "$DEST"/bomerang-*.tar.gz | tail -n +8 | xargs -r rm --
echo "Backup written: $DEST/bomerang-$STAMP.tar.gz"
