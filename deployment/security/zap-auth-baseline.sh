#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-https://127.0.0.1}"
REPORT_DIR="${2:-$(cd "$(dirname "$0")/../.." && pwd)/reports/security}"
mkdir -p "$REPORT_DIR"

# 需要本机可访问目标地址，并已信任证书或使用公开证书。
docker run --rm \
  -v "$REPORT_DIR:/zap/wrk:rw" \
  ghcr.io/zaproxy/zaproxy:stable \
  zap-baseline.py \
  -t "$TARGET" \
  -m 5 \
  -J zap-auth-report.json \
  -r zap-auth-report.html \
  -w zap-auth-report.md

echo "ZAP baseline report generated in: $REPORT_DIR"
