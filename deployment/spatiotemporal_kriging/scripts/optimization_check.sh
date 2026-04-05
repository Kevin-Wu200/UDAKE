#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_ROOT="$(cd "$ROOT_DIR/../.." && pwd)"
cd "$ROOT_DIR"

THRESHOLD_FILE="$ROOT_DIR/monitoring/optimization_thresholds.env"
if [[ ! -f "$THRESHOLD_FILE" ]]; then
  THRESHOLD_FILE="$ROOT_DIR/monitoring/optimization_thresholds.env.example"
fi

# shellcheck disable=SC1090
source "$THRESHOLD_FILE"

MIN_HIGH_PRIORITY_DOC_COUNT="${MIN_HIGH_PRIORITY_DOC_COUNT:-3}"
MIN_MEDIUM_PRIORITY_DOC_COUNT="${MIN_MEDIUM_PRIORITY_DOC_COUNT:-3}"
MIN_OPTIMIZATION_SCRIPT_COUNT="${MIN_OPTIMIZATION_SCRIPT_COUNT:-3}"
MAX_OPTIMIZATION_HEALTH_LATENCY_MS="${MAX_OPTIMIZATION_HEALTH_LATENCY_MS:-2500}"
REQUIRE_DISTRIBUTED_READY="${REQUIRE_DISTRIBUTED_READY:-1}"

errors=0
warnings=0

echo "[后续优化巡检] 开始执行..."

check_file_exists() {
  local file="$1"
  local label="$2"
  if [[ -f "$file" ]]; then
    echo "[PASS] ${label}: ${file}"
  else
    echo "[FAIL] ${label}缺失: ${file}"
    errors=$((errors + 1))
  fi
}

check_dir_exists() {
  local dir="$1"
  local label="$2"
  if [[ -d "$dir" ]]; then
    echo "[PASS] ${label}: ${dir}"
  else
    echo "[FAIL] ${label}缺失: ${dir}"
    errors=$((errors + 1))
  fi
}

check_file_exists "$ROOT_DIR/monitoring/optimization_thresholds.env.example" "优化阈值模板"
check_file_exists "$ROOT_DIR/scripts/optimization_check.sh" "优化巡检脚本"
check_file_exists "$PROJECT_ROOT/docs/spatiotemporal/ops/后续优化手册.md" "后续优化手册"

high_priority_docs=(
  "$PROJECT_ROOT/docs/spatiotemporal/algorithms.md"
  "$PROJECT_ROOT/docs/spatiotemporal/performance.md"
  "$PROJECT_ROOT/docs/spatiotemporal/ops/性能调优指南.md"
)

medium_priority_docs=(
  "$PROJECT_ROOT/docs/spatiotemporal/ops/质量标准手册.md"
  "$PROJECT_ROOT/docs/spatiotemporal/ops/风险管理手册.md"
  "$PROJECT_ROOT/docs/spatiotemporal/integration.md"
)

high_doc_count=0
for file in "${high_priority_docs[@]}"; do
  [[ -f "$file" ]] && high_doc_count=$((high_doc_count + 1))
done

if [[ "$high_doc_count" -lt "$MIN_HIGH_PRIORITY_DOC_COUNT" ]]; then
  echo "[FAIL] 高优先级文档覆盖不足: ${high_doc_count}/${MIN_HIGH_PRIORITY_DOC_COUNT}"
  errors=$((errors + 1))
else
  echo "[PASS] 高优先级文档覆盖达标: ${high_doc_count}/${MIN_HIGH_PRIORITY_DOC_COUNT}"
fi

medium_doc_count=0
for file in "${medium_priority_docs[@]}"; do
  [[ -f "$file" ]] && medium_doc_count=$((medium_doc_count + 1))
done

if [[ "$medium_doc_count" -lt "$MIN_MEDIUM_PRIORITY_DOC_COUNT" ]]; then
  echo "[WARN] 中优先级文档覆盖不足: ${medium_doc_count}/${MIN_MEDIUM_PRIORITY_DOC_COUNT}"
  warnings=$((warnings + 1))
else
  echo "[PASS] 中优先级文档覆盖达标: ${medium_doc_count}/${MIN_MEDIUM_PRIORITY_DOC_COUNT}"
fi

optimization_script_count="$(find "$ROOT_DIR/scripts" -maxdepth 1 -type f \( -name '*_check.sh' -o -name 'update.sh' \) | wc -l | tr -d ' ')"
if [[ "${optimization_script_count:-0}" -lt "$MIN_OPTIMIZATION_SCRIPT_COUNT" ]]; then
  echo "[FAIL] 优化相关脚本不足: ${optimization_script_count} < ${MIN_OPTIMIZATION_SCRIPT_COUNT}"
  errors=$((errors + 1))
else
  echo "[PASS] 优化相关脚本数量达标: ${optimization_script_count}"
fi

check_dir_exists "$PROJECT_ROOT/services/backend/app/core/spatiotemporal_kriging" "时空克里金核心模块"
check_dir_exists "$PROJECT_ROOT/deep_learning/models/spatiotemporal" "深度学习时空模型目录"
check_dir_exists "$PROJECT_ROOT/multi_objective_optimization" "多目标优化目录"

if [[ "$REQUIRE_DISTRIBUTED_READY" -eq 1 ]]; then
  if [[ -f "$ROOT_DIR/docker-compose.yml" && -f "$ROOT_DIR/monitoring/prometheus.yml" ]]; then
    echo "[PASS] 分布式运行基础条件满足（compose + prometheus）"
  else
    echo "[FAIL] 分布式运行基础条件缺失（需要 docker-compose.yml 与 monitoring/prometheus.yml）"
    errors=$((errors + 1))
  fi
fi

if curl -sS -m 3 http://127.0.0.1:8000/health >/dev/null 2>&1; then
  latency_ms="$(curl -sS -m 5 -o /dev/null -w '%{time_total}' http://127.0.0.1:8000/health | awk '{printf "%.0f", $1*1000}')"
  if [[ "${latency_ms:-0}" -gt "$MAX_OPTIMIZATION_HEALTH_LATENCY_MS" ]]; then
    echo "[WARN] 本地后端健康接口延迟偏高: ${latency_ms}ms > ${MAX_OPTIMIZATION_HEALTH_LATENCY_MS}ms"
    warnings=$((warnings + 1))
  else
    echo "[PASS] 本地后端健康接口延迟正常: ${latency_ms}ms"
  fi
else
  echo "[WARN] 未检测到本地后端服务，跳过健康延迟检查（127.0.0.1:8000/health）"
  warnings=$((warnings + 1))
fi

echo "[后续优化巡检] 完成：errors=${errors}, warnings=${warnings}"

if [[ "$errors" -gt 0 ]]; then
  exit 1
fi

exit 0
