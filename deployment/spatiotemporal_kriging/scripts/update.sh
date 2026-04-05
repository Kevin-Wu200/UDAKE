#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "执行更新前备份..."
"$ROOT_DIR/scripts/backup.sh"

echo "拉起新镜像并滚动更新..."
docker compose -f docker-compose.yml build backend frontend
docker compose -f docker-compose.yml up -d backend frontend nginx

echo "更新后健康检查..."
for i in {1..20}; do
  if curl -fsS http://127.0.0.1/health >/dev/null 2>&1; then
    echo "更新成功，健康检查通过。"
    exit 0
  fi
  sleep 3
done

echo "更新后健康检查失败，尝试回滚到最近备份。"
LATEST_BACKUP="$(find ./backups -mindepth 1 -maxdepth 1 -type d | sort | tail -n 1)"
if [[ -n "$LATEST_BACKUP" ]]; then
  "$ROOT_DIR/scripts/restore.sh" "$LATEST_BACKUP"
fi
exit 1
