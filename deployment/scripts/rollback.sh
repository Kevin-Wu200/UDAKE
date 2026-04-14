#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODULE_DIR="${DEPLOY_TARGET_DIR:-$ROOT_DIR/spatiotemporal_kriging}"
TRIGGER_FILE="$ROOT_DIR/rollback/rollback-trigger.env"

if [[ -f "$TRIGGER_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$TRIGGER_FILE"
fi

MAX_FAILED_HEALTHCHECKS="${MAX_FAILED_HEALTHCHECKS:-3}"
ROLLBACK_WINDOW_MINUTES="${ROLLBACK_WINDOW_MINUTES:-30}"

echo "[INFO] 回滚触发阈值: 健康检查失败次数=${MAX_FAILED_HEALTHCHECKS}, 时间窗口=${ROLLBACK_WINDOW_MINUTES}分钟"

LATEST_BACKUP="$(find "$MODULE_DIR/backups" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort | tail -n 1 || true)"
if [[ -z "$LATEST_BACKUP" ]]; then
  echo "[ERROR] 未找到可用备份，无法执行回滚。"
  exit 1
fi

echo "[INFO] 使用最近备份执行回滚: $LATEST_BACKUP"
"$MODULE_DIR/scripts/restore.sh" "$LATEST_BACKUP"
