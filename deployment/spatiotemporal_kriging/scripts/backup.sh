#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -f .env ]]; then
  # shellcheck disable=SC1091
  source .env
fi

TS="$(date +%Y%m%d_%H%M%S)"
BACKUP_ROOT="${BACKUP_ROOT:-./backups}"
TARGET_DIR="$BACKUP_ROOT/$TS"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-14}"

mkdir -p "$TARGET_DIR"

echo "备份 PostgreSQL..."
docker compose -f docker-compose.yml exec -T postgres \
  pg_dump -U udake -d udake_kriging --format=custom --compress=6 \
  > "$TARGET_DIR/postgres.dump"

echo "备份 Redis..."
docker compose -f docker-compose.yml exec -T redis \
  sh -c 'redis-cli SAVE >/dev/null && cat /data/dump.rdb' \
  > "$TARGET_DIR/redis.rdb"

echo "备份配置与日志..."
tar -czf "$TARGET_DIR/configs.tgz" .env docker-compose.yml nginx monitoring logging/logrotate.conf

echo "校验备份完整性..."
sha256sum "$TARGET_DIR"/* > "$TARGET_DIR/SHA256SUMS"

if [[ -n "${OFFSITE_BACKUP_DIR:-}" ]]; then
  mkdir -p "$OFFSITE_BACKUP_DIR"
  rsync -a "$TARGET_DIR" "$OFFSITE_BACKUP_DIR/"
  echo "已同步异地备份: $OFFSITE_BACKUP_DIR"
fi

find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -mtime "+$RETENTION_DAYS" -exec rm -rf {} +

echo "备份完成: $TARGET_DIR"
