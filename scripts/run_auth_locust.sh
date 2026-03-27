#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOCUST_FILE="$ROOT_DIR/services/backend/tests/performance/locust_auth.py"
REPORT_DIR="${AUTH_PERF_REPORT_DIR:-$ROOT_DIR/reports/auth_performance}"
TARGET_HOST="${AUTH_PERF_HOST:-http://127.0.0.1:8000}"

mkdir -p "$REPORT_DIR"

run_case() {
  local case_name="$1"
  local users="$2"
  local spawn_rate="$3"
  local run_time="$4"

  echo "[locust] case=$case_name users=$users spawn_rate=$spawn_rate run_time=$run_time host=$TARGET_HOST"
  locust \
    -f "$LOCUST_FILE" \
    --host "$TARGET_HOST" \
    --headless \
    --users "$users" \
    --spawn-rate "$spawn_rate" \
    --run-time "$run_time" \
    --csv "$REPORT_DIR/${case_name}" \
    --html "$REPORT_DIR/${case_name}.html"
}

# 负载测试：100并发，持续10分钟
run_case "auth_load_100u_10m" 100 20 "10m"

# 压力测试：500并发，持续5分钟
run_case "auth_stress_500u_5m" 500 100 "5m"

echo "[locust] done. reports in $REPORT_DIR"
