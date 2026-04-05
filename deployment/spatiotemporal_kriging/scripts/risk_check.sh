#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

THRESHOLD_FILE="$ROOT_DIR/monitoring/risk_thresholds.env"
if [[ ! -f "$THRESHOLD_FILE" ]]; then
  THRESHOLD_FILE="$ROOT_DIR/monitoring/risk_thresholds.env.example"
fi

# shellcheck disable=SC1090
source "$THRESHOLD_FILE"

MAX_DISK_PERCENT="${MAX_DISK_PERCENT:-85}"
MAX_BACKUP_AGE_HOURS="${MAX_BACKUP_AGE_HOURS:-24}"

errors=0
warnings=0

echo "[风险巡检] 开始执行..."

if curl -fsS http://127.0.0.1/health >/dev/null 2>&1; then
  echo "[PASS] 后端健康检查通过"
else
  echo "[FAIL] 后端健康检查失败"
  errors=$((errors + 1))
fi

if [[ -f "$ROOT_DIR/monitoring/alert_rules.yml" ]]; then
  echo "[PASS] 告警规则文件存在"
else
  echo "[FAIL] 告警规则文件缺失: monitoring/alert_rules.yml"
  errors=$((errors + 1))
fi

disk_line="$(df -Pk . | tail -n 1)"
disk_percent="$(echo "$disk_line" | awk '{print $5}' | tr -d '%')"
if [[ "${disk_percent:-0}" -gt "$MAX_DISK_PERCENT" ]]; then
  echo "[WARN] 磁盘使用率过高: ${disk_percent}% > ${MAX_DISK_PERCENT}%"
  warnings=$((warnings + 1))
else
  echo "[PASS] 磁盘使用率正常: ${disk_percent}%"
fi

latest_backup="$(find "$ROOT_DIR/backups" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort | tail -n 1 || true)"
if [[ -z "$latest_backup" ]]; then
  echo "[WARN] 未发现备份目录: $ROOT_DIR/backups"
  warnings=$((warnings + 1))
else
  now_epoch="$(date +%s)"
  if stat -f %m "$latest_backup" >/dev/null 2>&1; then
    backup_epoch="$(stat -f %m "$latest_backup")"
  else
    backup_epoch="$(stat -c %Y "$latest_backup")"
  fi
  age_hours="$(( (now_epoch - backup_epoch) / 3600 ))"
  if [[ "$age_hours" -gt "$MAX_BACKUP_AGE_HOURS" ]]; then
    echo "[WARN] 最新备份超过阈值: ${age_hours}h > ${MAX_BACKUP_AGE_HOURS}h"
    warnings=$((warnings + 1))
  else
    echo "[PASS] 备份时效正常: ${age_hours}h"
  fi
fi

echo "[风险巡检] 完成：errors=${errors}, warnings=${warnings}"

if [[ "$errors" -gt 0 ]]; then
  exit 1
fi

exit 0
