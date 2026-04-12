#!/usr/bin/env bash
set -u

BASE_URL="${1:-http://127.0.0.1:8000}"
BASE_URL="${BASE_URL%/}"

ENDPOINTS=(
  "/health"
  "/api/startup/health"
)

declare -i FAILURES=0

echo "[INFO] base url: ${BASE_URL}"

for path in "${ENDPOINTS[@]}"; do
  url="${BASE_URL}${path}"
  code=$(curl -sS -m 5 -o /tmp/udake_health_resp.json -w "%{http_code}" "${url}" 2>/dev/null)
  if [[ $? -ne 0 ]]; then
    code="000"
  fi
  if [[ "${code}" != "200" ]]; then
    echo "[FAIL] ${url} -> HTTP ${code}"
    FAILURES+=1
  else
    echo "[PASS] ${url} -> HTTP 200"
  fi
done

if [[ ${FAILURES} -eq 0 ]]; then
  echo "[STEP] JSON field checks"
  if ! python - <<'PY'
import json
from pathlib import Path

p = Path('/tmp/udake_health_resp.json')
if not p.exists():
    raise SystemExit(1)

data = json.loads(p.read_text(encoding='utf-8'))
if 'status' in data:
    print('[PASS] health json has status field')
elif 'ready' in data:
    print('[PASS] startup health json has ready field')
else:
    raise SystemExit('response missing expected fields')
PY
  then
    echo "[FAIL] json field checks failed"
    FAILURES+=1
  fi
fi

if [[ ${FAILURES} -gt 0 ]]; then
  echo "[FAIL] health_check finished with ${FAILURES} issue(s)"
  exit 1
fi

echo "[PASS] health_check passed"
