#!/usr/bin/env bash
set -euo pipefail

BACKUP_FILE="${1:-}"
if [[ -z "$BACKUP_FILE" ]]; then
  echo "usage: $0 <backup.dump|snapshot.sql.gz>" >&2
  exit 1
fi

: "${PGHOST:?PGHOST is required}"
: "${PGPORT:=5432}"
: "${PGUSER:?PGUSER is required}"
: "${PGDATABASE:?PGDATABASE is required}"
: "${PGPASSWORD:?PGPASSWORD is required}"

if [[ ! -f "$BACKUP_FILE" ]]; then
  echo "backup file not found: $BACKUP_FILE" >&2
  exit 1
fi

if [[ "$BACKUP_FILE" == *.dump ]]; then
  pg_restore -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE" --clean --if-exists --no-owner "$BACKUP_FILE"
elif [[ "$BACKUP_FILE" == *.sql.gz ]]; then
  gunzip -c "$BACKUP_FILE" | psql -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDATABASE"
else
  echo "unsupported file format: $BACKUP_FILE" >&2
  exit 1
fi

echo "restore finished from: $BACKUP_FILE"
