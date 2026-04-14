#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

export PYTHONPATH="${ROOT_DIR}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}"

TEST_FILE="tests/deep_learning/test_cross_model_stage2.py"
REPORT_FILE="tests/reports/cross-model-stage2-report.md"

echo "[1/2] 运行跨模型测试第二阶段用例..."
if [ -x "${ROOT_DIR}/venv/bin/pytest" ]; then
  PYTHONPATH="${PYTHONPATH}" "${ROOT_DIR}/venv/bin/pytest" -q "${TEST_FILE}"
else
  python3 -m pytest -q "${TEST_FILE}"
fi

echo "[2/2] 更新阶段报告时间戳..."
python3 - <<'PY'
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path

report_path = Path("tests/reports/cross-model-stage2-report.md")
text = report_path.read_text(encoding="utf-8") if report_path.exists() else "# 跨模型测试第二阶段报告\n"
marker = "- 最近执行时间(UTC): "
lines = [line for line in text.splitlines() if not line.startswith(marker)]
lines.append(f"{marker}{datetime.now(timezone.utc).isoformat()}")
report_path.parent.mkdir(parents=True, exist_ok=True)
report_path.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")
print(f"report={report_path}")
PY

echo "跨模型测试第二阶段执行完成。"
