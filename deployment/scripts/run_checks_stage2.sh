#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

"$ROOT_DIR/scripts/test_autoscaling.sh"
"$ROOT_DIR/scripts/verify_performance_baseline.sh"
"$ROOT_DIR/scripts/test_backup_restore.sh"
"$ROOT_DIR/scripts/test_disaster_recovery.sh"

echo "[INFO] 部署与运维阶段2校验完成。"
