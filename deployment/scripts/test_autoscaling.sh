#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
POLICY_FILE="$ROOT_DIR/autoscaling/autoscaling_policy.yml"

[[ -f "$POLICY_FILE" ]] || { echo "[ERROR] 未找到扩缩容策略文件: $POLICY_FILE"; exit 1; }

grep -q "min_replicas" "$POLICY_FILE" || { echo "[ERROR] 缺少 min_replicas 配置"; exit 1; }
grep -q "max_replicas" "$POLICY_FILE" || { echo "[ERROR] 缺少 max_replicas 配置"; exit 1; }
grep -q "cpu_utilization_percent" "$POLICY_FILE" || { echo "[ERROR] 缺少 CPU 阈值配置"; exit 1; }
grep -q "memory_utilization_percent" "$POLICY_FILE" || { echo "[ERROR] 缺少内存阈值配置"; exit 1; }
grep -q "requests_per_second" "$POLICY_FILE" || { echo "[ERROR] 缺少请求量阈值配置"; exit 1; }

echo "[INFO] 扩缩容策略配置校验通过。"
