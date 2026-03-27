#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-full}"
TS="$(date '+%Y%m%d_%H%M%S')"
BACKUP_DIR="${AUTH_BACKUP_DIR:-$(cd "$(dirname "$0")/.." && pwd)/deployment/backups}"
mkdir -p "$BACKUP_DIR"

: "${PGHOST:?PGHOST is required}"
: "${PGPORT:=5432}"
: "${PGUSER:?PGUSER is required}"
: "${PGDATABASE:?PGDATABASE is required}"
: "${PGPASSWORD:?PGPASSWORD is required}"

FULL_FILE="$BACKUP_DIR/auth_full_${TS}.dump"
INCR_FILE="$BACKUP_DIR/auth_hourly_${TS}.sql.gz"

if [[ "$MODE" == "full" ]]; then
  pg_dump -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" -Fc -f "$FULL_FILE"
  shasum -a 256 "$FULL_FILE" > "$FULL_FILE.sha256"
  echo "full backup created: $FULL_FILE"
elif [[ "$MODE" == "hourly" ]]; then
  # PostgreSQL 无原生逻辑增量导出；这里使用 data-only 快照作为小时级增量近似。
  pg_dump -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" --data-only --inserts | gzip > "$INCR_FILE"
  shasum -a 256 "$INCR_FILE" > "$INCR_FILE.sha256"
  echo "hourly snapshot created: $INCR_FILE"
else
  echo "usage: $0 [full|hourly]" >&2
  exit 1
fi
