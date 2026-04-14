#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ALERT_FILE="$ROOT_DIR/monitoring/alert_rules.yml"

if [[ ! -f "$ALERT_FILE" ]]; then
  echo "[ERROR] 告警规则文件不存在: $ALERT_FILE"
  exit 1
fi

if command -v promtool >/dev/null 2>&1; then
  promtool check rules "$ALERT_FILE"
  echo "[INFO] 告警规则语法校验通过。"
else
  echo "[WARN] promtool 不存在，仅执行基础文本校验。"
  rg -n "^\s*- alert:" "$ALERT_FILE" >/dev/null
  echo "[INFO] 检测到告警规则定义。"
fi
