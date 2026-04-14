#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODULE_DIR="${DEPLOY_TARGET_DIR:-$ROOT_DIR/spatiotemporal_kriging}"

if [[ ! -d "$MODULE_DIR" ]]; then
  echo "[ERROR] 部署目标目录不存在: $MODULE_DIR"
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "[ERROR] 未安装 docker，请先安装 Docker Engine。"
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "[ERROR] 未安装 docker compose 插件。"
  exit 1
fi

if [[ ! -f "$MODULE_DIR/.env" ]]; then
  cp "$MODULE_DIR/.env.example" "$MODULE_DIR/.env"
  echo "[INFO] 已生成默认配置: $MODULE_DIR/.env"
fi

mkdir -p "$MODULE_DIR/backups" "$MODULE_DIR/logging" "$MODULE_DIR/logging/nginx" "$MODULE_DIR/certs"

echo "[INFO] 基础安装检查完成。"
echo "[INFO] 下一步: ./deployment/scripts/configure.sh"
