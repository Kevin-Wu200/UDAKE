#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "用法: $0 <备份目录>"
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODULE_DIR="${DEPLOY_TARGET_DIR:-$ROOT_DIR/spatiotemporal_kriging}"

"$MODULE_DIR/scripts/restore.sh" "$1"
