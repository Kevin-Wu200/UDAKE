#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASELINE_FILE="$ROOT_DIR/autoscaling/performance_baseline.yml"

[[ -f "$BASELINE_FILE" ]] || { echo "[ERROR] 未找到性能基线文件: $BASELINE_FILE"; exit 1; }

for metric in api_p95_latency_seconds api_p99_latency_seconds request_success_rate error_rate_5xx cpu_utilization_percent memory_utilization_percent; do
  grep -q "name: $metric" "$BASELINE_FILE" || { echo "[ERROR] 性能基线缺少指标: $metric"; exit 1; }
done

grep -q "anomaly_detection" "$BASELINE_FILE" || { echo "[ERROR] 缺少异常识别配置"; exit 1; }
grep -q "alerting" "$BASELINE_FILE" || { echo "[ERROR] 缺少性能告警配置"; exit 1; }

echo "[INFO] 性能基线配置校验通过。"
