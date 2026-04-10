#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

export PYTHONPATH="${ROOT_DIR}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}"

TEST_FILES=(
  "tests/deep_learning/test_gnn_kriging_adapter_stage1.py"
  "tests/deep_learning/test_gnn_kriging_adapter_stage2.py"
  "tests/deep_learning/test_attention_kriging_adapter_stage1.py"
  "tests/deep_learning/test_attention_kriging_adapter_stage2.py"
  "tests/deep_learning/test_residual_kriging_adapter_stage1.py"
  "tests/deep_learning/test_residual_kriging_adapter_stage2.py"
)

UV_BASE=(
  uv run
  --with pytest
  --with coverage
  --with numpy
  --with scipy
  --with scikit-learn
  --with pykrige
  --with pyshp
)

echo "[1/2] 运行 GNN/Attention/Residual-Kriging 适配器测试..."
"${UV_BASE[@]}" coverage run -m pytest --noconftest "${TEST_FILES[@]}" -q

echo "[2/2] 统计 explainer 覆盖率并校验 >= 80%..."
"${UV_BASE[@]}" coverage report \
  --include="services/backend/app/dl_services/gnn_kriging_explainer.py,services/backend/app/dl_services/attention_kriging_explainer.py,services/backend/app/dl_services/residual_kriging_explainer.py" \
  --fail-under=80 \
  -m

echo "Kriging 适配器测试与覆盖率校验已完成。"
