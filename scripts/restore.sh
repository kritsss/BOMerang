#!/usr/bin/env bash
# Restore a backup made by scripts/backup.sh. REPLACES all current BOMerang data.
#   bash scripts/restore.sh ~/bomerang-backups/bomerang-YYYYMMDD-HHMMSS.tar.gz
set -euo pipefail
[ $# -eq 1 ] && [ -f "$1" ] || { echo "usage: $0 <backup.tar.gz>"; exit 1; }
BK=$(cd "$(dirname "$1")" && pwd)/$(basename "$1")
cd "$(dirname "$0")/.."
DC="docker compose -f docker-compose.prod.yml"
command -v docker >/dev/null && docker info >/dev/null 2>&1 || DC="sudo $DC"
read -r -p "This replaces all current BOMerang data with $BK. Type yes to continue: " ok
[ "$ok" = "yes" ] || { echo "Cancelled."; exit 1; }
$DC stop api
$DC run --rm --no-deps -T -v "$BK":/restore.tar.gz:ro --entrypoint sh api -c 'find /data -mindepth 1 -delete && tar xzf /restore.tar.gz -C /data'
$DC start api
echo "Restored from $BK"
