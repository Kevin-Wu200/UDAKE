#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "用法: $0 <备份目录>"
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

BACKUP_DIR="$1"
if [[ ! -d "$BACKUP_DIR" ]]; then
  echo "备份目录不存在: $BACKUP_DIR"
  exit 1
fi

if [[ ! -f "$BACKUP_DIR/postgres.dump" || ! -f "$BACKUP_DIR/redis.rdb" ]]; then
  echo "备份目录缺少必要文件（postgres.dump / redis.rdb）"
  exit 1
fi

echo "停止应用层服务..."
docker compose -f docker-compose.yml stop backend frontend nginx

echo "恢复 PostgreSQL..."
docker compose -f docker-compose.yml exec -T postgres \
  bash -lc 'dropdb -U udake --if-exists udake_kriging && createdb -U udake udake_kriging'
docker compose -f docker-compose.yml exec -T postgres \
  pg_restore -U udake -d udake_kriging < "$BACKUP_DIR/postgres.dump"

echo "恢复 Redis..."
docker compose -f docker-compose.yml stop redis
docker cp "$BACKUP_DIR/redis.rdb" udake-kriging-redis:/data/dump.rdb
docker compose -f docker-compose.yml start redis

echo "恢复配置包..."
if [[ -f "$BACKUP_DIR/configs.tgz" ]]; then
  tar -xzf "$BACKUP_DIR/configs.tgz" -C "$ROOT_DIR"
fi

echo "重启全部服务..."
docker compose -f docker-compose.yml up -d

echo "恢复完成。"
