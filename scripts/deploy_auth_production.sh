#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="${AUTH_DEPLOY_ENV_FILE:-$ROOT_DIR/deployment/env/auth.production.env}"
COMPOSE_FILE="$ROOT_DIR/deployment/docker-compose.auth.yml"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "missing env file: $ENV_FILE" >&2
  exit 1
fi

cd "$ROOT_DIR"

echo "[1/6] build frontend assets"
npm run build
npm run build --prefix apps/admin-frontend

echo "[2/6] start containers"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --build

echo "[3/6] run alembic migration"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" exec -T backend alembic upgrade head

echo "[4/6] health checks"
curl -fsS http://127.0.0.1/health >/dev/null || true
curl -fsSk https://127.0.0.1/health >/dev/null

echo "[5/6] smoke test auth endpoints"
curl -fsSk https://127.0.0.1/api/auth/csrf-token >/dev/null

echo "[6/6] deployment completed"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" ps
