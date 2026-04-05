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
health_ok=0

echo "[风险巡检] 开始执行..."

# 健康检查优先级：
# 1) Docker Compose 后端容器内部 /health
# 2) 宿主机本地后端 127.0.0.1:8000/health
# 3) Nginx 入口 127.0.0.1/health
if command -v docker >/dev/null 2>&1 && docker compose -f "$ROOT_DIR/docker-compose.yml" ps backend >/dev/null 2>&1; then
  if docker compose -f "$ROOT_DIR/docker-compose.yml" ps --status running backend 2>/dev/null | grep -q backend; then
    if docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T backend curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
      echo "[PASS] 后端健康检查通过（docker compose: backend）"
      health_ok=1
    fi
  fi
fi

if [[ "$health_ok" -eq 0 ]] && curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
  echo "[PASS] 后端健康检查通过（host:127.0.0.1:8000）"
  health_ok=1
fi

if [[ "$health_ok" -eq 0 ]] && curl -fsS http://127.0.0.1/health >/dev/null 2>&1; then
  echo "[PASS] 后端健康检查通过（nginx:127.0.0.1）"
  health_ok=1
fi

if [[ "$health_ok" -eq 0 ]]; then
  echo "[FAIL] 后端健康检查失败：未检测到可用后端（compose/backend、127.0.0.1:8000、127.0.0.1）"
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
