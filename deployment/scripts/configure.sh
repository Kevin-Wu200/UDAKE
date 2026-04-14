#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MODULE_DIR="${DEPLOY_TARGET_DIR:-$ROOT_DIR/spatiotemporal_kriging}"
CONFIG_DIR="$ROOT_DIR/config"

if [[ ! -d "$MODULE_DIR" ]]; then
  echo "[ERROR] 部署目标目录不存在: $MODULE_DIR"
  exit 1
fi

if [[ ! -f "$MODULE_DIR/.env" ]]; then
  echo "[ERROR] 缺少 $MODULE_DIR/.env，请先执行 install.sh 或手动创建。"
  exit 1
fi

for f in \
  "$CONFIG_DIR/database.yml" \
  "$CONFIG_DIR/cache.yml" \
  "$CONFIG_DIR/logging.yml" \
  "$CONFIG_DIR/security.yml" \
  "$CONFIG_DIR/performance.yml" \
  "$CONFIG_DIR/resources.yml" \
  "$CONFIG_DIR/network.yml"; do
  if [[ ! -f "$f" ]]; then
    echo "[ERROR] 缺少配置文件: $f"
    exit 1
  fi
done

echo "[INFO] 配置文件存在性检查通过。"
"$CONFIG_DIR/validate_config.sh" "$MODULE_DIR/.env"

echo "[INFO] 配置完成。"
