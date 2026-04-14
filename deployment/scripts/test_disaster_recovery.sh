#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DR_DIR="$ROOT_DIR/disaster-recovery"

for file in scenarios.md recovery_strategy.md recovery_runbook.md resource_checklist.md drill_plan.md training_plan.md; do
  [[ -f "$DR_DIR/$file" ]] || { echo "[ERROR] 缺少灾备文档: $DR_DIR/$file"; exit 1; }
done

grep -q "RTO" "$DR_DIR/recovery_strategy.md" || { echo "[ERROR] 恢复策略缺少 RTO 指标"; exit 1; }
grep -q "RPO" "$DR_DIR/recovery_strategy.md" || { echo "[ERROR] 恢复策略缺少 RPO 指标"; exit 1; }
grep -q "执行步骤" "$DR_DIR/recovery_runbook.md" || { echo "[ERROR] 恢复流程未定义执行步骤"; exit 1; }

echo "[INFO] 灾难恢复文档校验通过。"
