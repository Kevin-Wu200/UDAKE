#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMP_DIR="${ROOT_DIR}/.tmp-windows-build"

cleanup() {
  rm -rf "${TEMP_DIR}"
}
trap cleanup EXIT

mkdir -p "${TEMP_DIR}"

echo "[build-windows] 1/5 构建前端生产资源"
cd "${ROOT_DIR}"
npm run build:prod

echo "[build-windows] 2/5 更新构建配置"
echo "[build-windows] 当前无需额外配置更新，跳过"

echo "[build-windows] 3/5 执行 Windows 构建 (nsis + zip)"
npm run build:electron -- --win

echo "[build-windows] 4/5 复制最新 EXE 到项目根目录"
node scripts/copy-windows-artifact.js

echo "[build-windows] 5/5 清理临时文件"
cleanup

echo "[build-windows] 完成，产物位于 ${ROOT_DIR}/UDAKE.exe"
