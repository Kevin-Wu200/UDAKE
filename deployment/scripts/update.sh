#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODULE_DIR="${DEPLOY_TARGET_DIR:-$ROOT_DIR/spatiotemporal_kriging}"

"$ROOT_DIR/scripts/backup.sh"

cd "$MODULE_DIR"
docker compose -f docker-compose.yml build backend frontend
docker compose -f docker-compose.yml up -d backend frontend nginx

if curl -fsS http://127.0.0.1/health >/dev/null 2>&1; then
  echo "[INFO] 更新成功，健康检查通过。"
  exit 0
fi

echo "[WARN] 更新后健康检查失败，触发回滚。"
"$ROOT_DIR/scripts/rollback.sh"
