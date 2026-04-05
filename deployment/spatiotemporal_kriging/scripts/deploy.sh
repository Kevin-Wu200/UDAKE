#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f .env ]]; then
  echo "未找到 .env，请先从 .env.example 复制并填写生产配置。"
  exit 1
fi

mkdir -p backups/postgres logging/nginx certs

echo "[1/4] 校验 Compose 配置"
docker compose -f docker-compose.yml config >/dev/null

echo "[2/4] 构建镜像"
docker compose -f docker-compose.yml build backend frontend

echo "[3/4] 启动服务"
docker compose -f docker-compose.yml up -d postgres redis backend frontend nginx prometheus

echo "[4/4] 健康检查"
for i in {1..20}; do
  if curl -fsS http://127.0.0.1/health >/dev/null 2>&1; then
    echo "部署成功，健康检查通过。"
    exit 0
  fi
  sleep 3
done

echo "部署完成但健康检查未通过，请执行: docker compose -f docker-compose.yml logs --tail=200"
exit 1
