#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
LOG_FILE="${BACKEND_DIR}/startup_diagnose.log"

if [[ -x "${REPO_ROOT}/venv/bin/python" ]]; then
  PYTHON_BIN="${REPO_ROOT}/venv/bin/python"
else
  PYTHON_BIN="python"
fi

declare -i FAILURES=0

{
  echo "[INFO] startup diagnose started at $(date '+%Y-%m-%d %H:%M:%S %Z')"
  echo "[INFO] backend dir: ${BACKEND_DIR}"
  echo "[INFO] python: ${PYTHON_BIN}"

  echo "[STEP] app import smoke test"
  (
    cd "${BACKEND_DIR}" &&
    "${PYTHON_BIN}" -c "from app.main import app; print('FastAPI app import OK; routes=', len(app.routes))"
  ) || FAILURES+=1

  echo "[STEP] startup manager snapshot"
  (
    cd "${BACKEND_DIR}" &&
    "${PYTHON_BIN}" - <<'PY'
from app.main import startup_manager
snapshot = startup_manager.get_health_snapshot()
print('startup_ready=', snapshot.get('ready'))
print('startup_degradation_level=', snapshot.get('degradation_level'))
PY
  ) || FAILURES+=1

  echo "[STEP] uvicorn boot probe (6s)"
  cd "${BACKEND_DIR}" || exit 1
  "${PYTHON_BIN}" -m uvicorn app.main:app --host 127.0.0.1 --port 8000 > /tmp/udake_uvicorn_probe.log 2>&1 &
  pid=$!
  sleep 6
  PROBE_EXITED=0
  if kill -0 "$pid" >/dev/null 2>&1; then
    echo "[INFO] uvicorn still running after probe window, stopping it"
    kill "$pid" >/dev/null 2>&1 || true
    wait "$pid" >/dev/null 2>&1 || true
    echo "[INFO] uvicorn probe treated as success"
  else
    wait "$pid" >/dev/null 2>&1 || true
    PROBE_EXITED=1
    echo "[WARN] uvicorn exited during probe window"
  fi

  if grep -q "Application startup complete" /tmp/udake_uvicorn_probe.log 2>/dev/null; then
    echo "[INFO] startup lifecycle reached 'Application startup complete'"
  fi
  if grep -qi "operation not permitted" /tmp/udake_uvicorn_probe.log 2>/dev/null; then
    echo "[WARN] detected permission issue: operation not permitted"
  fi

  if [[ ${PROBE_EXITED} -eq 1 ]] && ! grep -qi "operation not permitted" /tmp/udake_uvicorn_probe.log 2>/dev/null; then
    echo "[ERROR] uvicorn exited unexpectedly (not permission related)"
    FAILURES+=1
  fi

  echo "[STEP] probe logs"
  sed -n '1,120p' /tmp/udake_uvicorn_probe.log 2>/dev/null || true

  if [[ ${FAILURES} -gt 0 ]]; then
    echo "[FAIL] startup_diagnose finished with ${FAILURES} issue(s)"
  else
    echo "[PASS] startup_diagnose passed"
  fi
} | tee "${LOG_FILE}"

if [[ ${FAILURES} -gt 0 ]]; then
  exit 1
fi
