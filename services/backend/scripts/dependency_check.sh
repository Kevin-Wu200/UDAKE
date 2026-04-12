#!/usr/bin/env bash
set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

if [[ -x "${REPO_ROOT}/venv/bin/python" ]]; then
  PYTHON_BIN="${REPO_ROOT}/venv/bin/python"
else
  PYTHON_BIN="python"
fi

echo "[INFO] Repo root: ${REPO_ROOT}"
echo "[INFO] Python: ${PYTHON_BIN}"

declare -i FAILURES=0

echo "[STEP] pip check"
if ! "${PYTHON_BIN}" -m pip check; then
  echo "[ERROR] pip check failed"
  FAILURES+=1
fi

echo "[STEP] package presence"
REQUIRED_PACKAGES=(
  GDAL
  PyKrige
  gstools
  torch
  torch-geometric
  torch-scatter
  torch-sparse
  scikit-learn
  lime
  shap
  redis
  celery
  numpy
  scipy
  pandas
)

for pkg in "${REQUIRED_PACKAGES[@]}"; do
  if ! "${PYTHON_BIN}" -m pip show "${pkg}" >/dev/null 2>&1; then
    echo "[MISSING] ${pkg}"
    FAILURES+=1
  fi
done

echo "[STEP] import checks"
IMPORT_TARGETS=(
  "from osgeo import gdal; print('GDAL', gdal.__version__)"
  "from pykrige.ok import OrdinaryKriging; print('PyKrige OK')"
  "import gstools; print('gstools', gstools.__version__)"
  "import torch; print('torch', torch.__version__)"
  "import torch_geometric; print('torch_geometric', torch_geometric.__version__)"
  "import torch_scatter; print('torch_scatter OK')"
  "import torch_sparse; print('torch_sparse OK')"
  "import sklearn; print('sklearn', sklearn.__version__)"
  "import lime; print('lime OK')"
  "import shap; print('shap', shap.__version__)"
  "import numpy, scipy, pandas; print('numpy/scipy/pandas', numpy.__version__, scipy.__version__, pandas.__version__)"
)

for code in "${IMPORT_TARGETS[@]}"; do
  if ! "${PYTHON_BIN}" -c "${code}" >/dev/null 2>&1; then
    echo "[ERROR] import failed: ${code}"
    FAILURES+=1
  fi
done

if [[ ${FAILURES} -gt 0 ]]; then
  echo "[FAIL] dependency_check finished with ${FAILURES} issue(s)"
  exit 1
fi

echo "[PASS] dependency_check passed"
