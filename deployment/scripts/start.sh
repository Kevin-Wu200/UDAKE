#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODULE_DIR="${DEPLOY_TARGET_DIR:-$ROOT_DIR/spatiotemporal_kriging}"

cd "$MODULE_DIR"
docker compose -f docker-compose.yml up -d postgres redis backend frontend nginx prometheus

echo "[INFO] 服务已启动。"
