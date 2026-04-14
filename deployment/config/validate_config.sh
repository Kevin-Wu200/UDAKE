#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_ENV="$ROOT_DIR/spatiotemporal_kriging/.env"
if [[ ! -f "$DEFAULT_ENV" ]]; then
  DEFAULT_ENV="$ROOT_DIR/spatiotemporal_kriging/.env.example"
fi
MODULE_ENV="${1:-$DEFAULT_ENV}"

if [[ ! -f "$MODULE_ENV" ]]; then
  echo "[ERROR] 未找到环境变量文件: $MODULE_ENV"
  exit 1
fi

required_env_keys=(
  DATABASE_URL
  REDIS_URL
  LOG_LEVEL
  AUTH_JWT_SECRET
  AUTH_ENCRYPTION_KEY
  DOMAIN
  PORT
)

missing=0
for key in "${required_env_keys[@]}"; do
  if ! rg -q "^${key}=" "$MODULE_ENV"; then
    echo "[FAIL] 缺少关键配置: ${key}"
    missing=$((missing + 1))
  fi
done

if ! rg -q '^DATABASE_URL=postgresql' "$MODULE_ENV"; then
  echo "[FAIL] DATABASE_URL 必须使用 postgresql 协议"
  missing=$((missing + 1))
fi

if ! rg -q '^REDIS_URL=redis://' "$MODULE_ENV"; then
  echo "[FAIL] REDIS_URL 必须使用 redis:// 格式"
  missing=$((missing + 1))
fi

if rg -q '^LOG_LEVEL=(DEBUG|INFO|WARNING|ERROR|CRITICAL)$' "$MODULE_ENV"; then
  echo "[PASS] LOG_LEVEL 取值合法"
else
  echo "[FAIL] LOG_LEVEL 必须为 DEBUG/INFO/WARNING/ERROR/CRITICAL"
  missing=$((missing + 1))
fi

secret_value="$(rg '^AUTH_JWT_SECRET=' "$MODULE_ENV" | head -n1 | cut -d= -f2- || true)"
if [[ "${#secret_value}" -lt 16 ]]; then
  echo "[FAIL] AUTH_JWT_SECRET 长度过短"
  missing=$((missing + 1))
fi

encryption_value="$(rg '^AUTH_ENCRYPTION_KEY=' "$MODULE_ENV" | head -n1 | cut -d= -f2- || true)"
if [[ "${#encryption_value}" -lt 16 ]]; then
  echo "[FAIL] AUTH_ENCRYPTION_KEY 长度过短"
  missing=$((missing + 1))
fi

if [[ "$missing" -gt 0 ]]; then
  echo "[ERROR] 配置校验失败，总计问题: $missing"
  exit 1
fi

echo "[INFO] 配置校验通过: $MODULE_ENV"
