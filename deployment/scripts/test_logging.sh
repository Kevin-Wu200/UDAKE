#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="${LOG_DIR:-$ROOT_DIR/spatiotemporal_kriging/logging}"

mkdir -p "$LOG_DIR"
TEST_LOG="$LOG_DIR/collection-test.log"

echo "$(date '+%F %T') level=INFO msg=log_pipeline_test service=udake-kriging" >> "$TEST_LOG"

if rg -q "log_pipeline_test" "$TEST_LOG"; then
  echo "[INFO] 日志写入与检索测试通过: $TEST_LOG"
  exit 0
fi

echo "[ERROR] 日志测试失败。"
exit 1
