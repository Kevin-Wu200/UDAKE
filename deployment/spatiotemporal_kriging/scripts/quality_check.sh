#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_ROOT="$(cd "$ROOT_DIR/../.." && pwd)"
cd "$ROOT_DIR"

THRESHOLD_FILE="$ROOT_DIR/monitoring/quality_thresholds.env"
if [[ ! -f "$THRESHOLD_FILE" ]]; then
  THRESHOLD_FILE="$ROOT_DIR/monitoring/quality_thresholds.env.example"
fi

# shellcheck disable=SC1090
source "$THRESHOLD_FILE"

MIN_TEST_FILE_COUNT="${MIN_TEST_FILE_COUNT:-6}"
MIN_ST_TEST_FILE_COUNT="${MIN_ST_TEST_FILE_COUNT:-6}"
MIN_DOC_FILE_COUNT="${MIN_DOC_FILE_COUNT:-6}"
MIN_COVERAGE_PERCENT="${MIN_COVERAGE_PERCENT:-80}"
MAX_API_LATENCY_MS="${MAX_API_LATENCY_MS:-2000}"

errors=0
warnings=0

echo "[质量巡检] 开始执行..."

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

check_file_exists "$ROOT_DIR/monitoring/quality_thresholds.env.example" "质量阈值模板"
check_file_exists "$ROOT_DIR/scripts/risk_check.sh" "风险巡检脚本"
check_file_exists "$ROOT_DIR/scripts/quality_check.sh" "质量巡检脚本"

required_docs=(
  "$PROJECT_ROOT/docs/spatiotemporal/API接口文档.md"
  "$PROJECT_ROOT/docs/spatiotemporal/integration.md"
  "$PROJECT_ROOT/docs/spatiotemporal/ops/部署手册.md"
  "$PROJECT_ROOT/docs/spatiotemporal/ops/运维手册.md"
  "$PROJECT_ROOT/docs/spatiotemporal/ops/故障排查指南.md"
  "$PROJECT_ROOT/docs/spatiotemporal/ops/质量标准手册.md"
)

doc_count=0
for file in "${required_docs[@]}"; do
  if [[ -f "$file" ]]; then
    doc_count=$((doc_count + 1))
  fi
done

if [[ "$doc_count" -lt "$MIN_DOC_FILE_COUNT" ]]; then
  echo "[FAIL] 文档完整性不足: ${doc_count}/${MIN_DOC_FILE_COUNT}"
  errors=$((errors + 1))
else
  echo "[PASS] 文档完整性满足阈值: ${doc_count}/${MIN_DOC_FILE_COUNT}"
fi

test_count="$(find "$PROJECT_ROOT/services/backend/tests" -maxdepth 1 -type f -name 'test_*.py' | wc -l | tr -d ' ')"
if [[ "${test_count:-0}" -lt "$MIN_TEST_FILE_COUNT" ]]; then
  echo "[FAIL] 后端测试文件数量不足: ${test_count} < ${MIN_TEST_FILE_COUNT}"
  errors=$((errors + 1))
else
  echo "[PASS] 后端测试文件数量达标: ${test_count}"
fi

st_test_count="$(find "$PROJECT_ROOT/services/backend/tests" -maxdepth 2 -type f -name 'test_st_*.py' | wc -l | tr -d ' ')"
if [[ "${st_test_count:-0}" -lt "$MIN_ST_TEST_FILE_COUNT" ]]; then
  echo "[FAIL] 时空克里金专项测试数量不足: ${st_test_count} < ${MIN_ST_TEST_FILE_COUNT}"
  errors=$((errors + 1))
else
  echo "[PASS] 时空克里金专项测试数量达标: ${st_test_count}"
fi

coverage_xml="$PROJECT_ROOT/coverage.xml"
if [[ -f "$coverage_xml" ]]; then
  coverage_percent="$(awk -F'"' '/<coverage/{for(i=1;i<=NF;i++){if($i=="line-rate"){print $(i+2); exit}}}' "$coverage_xml" 2>/dev/null || true)"
  if [[ -n "$coverage_percent" ]]; then
    coverage_value="$(awk -v n="$coverage_percent" 'BEGIN{printf "%.0f", n*100}')"
    if [[ "$coverage_value" -lt "$MIN_COVERAGE_PERCENT" ]]; then
      echo "[WARN] 代码覆盖率低于阈值: ${coverage_value}% < ${MIN_COVERAGE_PERCENT}%"
      warnings=$((warnings + 1))
    else
      echo "[PASS] 代码覆盖率达标: ${coverage_value}%"
    fi
  else
    echo "[WARN] 覆盖率文件存在但解析失败: ${coverage_xml}"
    warnings=$((warnings + 1))
  fi
else
  echo "[WARN] 未找到 coverage.xml，跳过覆盖率检查"
  warnings=$((warnings + 1))
fi

if curl -sS -m 3 http://127.0.0.1:8000/health >/dev/null 2>&1; then
  latency_ms="$(curl -sS -m 5 -o /dev/null -w '%{time_total}' http://127.0.0.1:8000/health | awk '{printf "%.0f", $1*1000}')"
  if [[ "${latency_ms:-0}" -gt "$MAX_API_LATENCY_MS" ]]; then
    echo "[WARN] 本地后端延迟偏高: ${latency_ms}ms > ${MAX_API_LATENCY_MS}ms"
    warnings=$((warnings + 1))
  else
    echo "[PASS] 本地后端延迟正常: ${latency_ms}ms"
  fi
else
  echo "[WARN] 未检测到本地后端服务，跳过延迟检查（127.0.0.1:8000/health）"
  warnings=$((warnings + 1))
fi

echo "[质量巡检] 完成：errors=${errors}, warnings=${warnings}"

if [[ "$errors" -gt 0 ]]; then
  exit 1
fi

exit 0
