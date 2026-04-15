#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMP_DIR="${ROOT_DIR}/.tmp-mac-build"

cleanup() {
  rm -rf "${TEMP_DIR}"
}
trap cleanup EXIT

mkdir -p "${TEMP_DIR}"

echo "[build-mac] 1/4 构建前端生产资源"
cd "${ROOT_DIR}"
npm run build:prod

echo "[build-mac] 2/4 执行 macOS 构建 (dmg + zip)"
npm run build:electron -- --mac

echo "[build-mac] 3/4 复制最新 DMG 到项目根目录"
node scripts/copy-mac-artifact.js

echo "[build-mac] 4/4 清理临时文件"
cleanup

echo "[build-mac] 完成，产物位于 ${ROOT_DIR}/UDAKE.dmg"
