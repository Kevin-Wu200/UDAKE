#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

"$ROOT_DIR/config/validate_config.sh"
"$ROOT_DIR/scripts/test_alerts.sh"
"$ROOT_DIR/scripts/test_logging.sh"

echo "[INFO] 部署与运维阶段1校验完成。"
