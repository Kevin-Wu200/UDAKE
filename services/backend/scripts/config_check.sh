#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
ENV_FILE="${REPO_ROOT}/configs/env/.env"

if [[ -x "${REPO_ROOT}/venv/bin/python" ]]; then
  PYTHON_BIN="${REPO_ROOT}/venv/bin/python"
else
  PYTHON_BIN="python"
fi

declare -i FAILURES=0

echo "[INFO] Repo root: ${REPO_ROOT}"
echo "[INFO] Env file: ${ENV_FILE}"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "[ERROR] missing env file: ${ENV_FILE}"
  exit 1
fi

REQUIRED_KEYS=(
  DATABASE_URL
  AUTH_DATABASE_URL
  REDIS_ENABLED
  REDIS_HOST
  REDIS_PORT
  REDIS_DB
  AUTH_DB_REQUIRE_SSL
  AUTH_DB_SSLMODE
  IPCONFIG
)

echo "[STEP] required key checks"
for key in "${REQUIRED_KEYS[@]}"; do
  if ! grep -qE "^${key}=" "${ENV_FILE}"; then
    echo "[MISSING] ${key}"
    FAILURES+=1
  fi
done

echo "[STEP] placeholder checks"
if grep -q "^GEOSCENE_API_KEY=YOUR_GEOSCENE_API_KEY_HERE" "${ENV_FILE}"; then
  echo "[WARN] GEOSCENE_API_KEY is still placeholder"
fi
if grep -q "^TIANDITU_API_KEY=YOUR_TIANDITU_API_KEY_HERE" "${ENV_FILE}"; then
  echo "[WARN] TIANDITU_API_KEY is still placeholder"
fi

echo "[STEP] runtime settings checks"
if ! (
  cd "${REPO_ROOT}/services/backend" &&
  "${PYTHON_BIN}" - <<'PY'
from app.config import settings

print(f"ENV_FILE={settings.model_config.get('env_file')}")
print(f"DATABASE_URL={settings.DATABASE_URL}")
print(f"AUTH_DATABASE_URL={settings.AUTH_DATABASE_URL}")
print(f"REDIS_ENABLED={settings.REDIS_ENABLED}")
print(f"RESULTS_DIR={settings.RESULTS_DIR}")
print(f"ANDROID_APK_DIR={settings.ANDROID_APK_DIR}")

missing = []
if not settings.RESULTS_DIR.exists():
    missing.append(str(settings.RESULTS_DIR))
if not settings.ANDROID_APK_DIR.exists():
    missing.append(str(settings.ANDROID_APK_DIR))

if missing:
    raise SystemExit("missing directories: " + ", ".join(missing))
PY
); then
  echo "[ERROR] settings load or directory checks failed"
  FAILURES+=1
fi

if [[ ${FAILURES} -gt 0 ]]; then
  echo "[FAIL] config_check finished with ${FAILURES} issue(s)"
  exit 1
fi

echo "[PASS] config_check passed"
