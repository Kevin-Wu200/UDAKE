#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/venv/bin/python}"
PYTEST_BIN="${PYTEST_BIN:-$ROOT_DIR/venv/bin/pytest}"
FULL_BACKEND=0
SKIP_BENCHMARK=0

usage() {
  cat <<USAGE
用法: $(basename "$0") [--full-backend] [--skip-benchmark]

选项:
  --full-backend     额外运行 services/backend/tests 的完整单元测试套件
  --skip-benchmark   跳过性能基准脚本
USAGE
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --full-backend)
      FULL_BACKEND=1
      shift
      ;;
    --skip-benchmark)
      SKIP_BENCHMARK=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "未知参数: $1"
      usage
      exit 2
      ;;
  esac
done

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "未找到 Python 可执行文件: $PYTHON_BIN"
  echo "请先创建虚拟环境，例如: python3 -m venv venv"
  exit 1
fi

if [[ ! -x "$PYTEST_BIN" ]]; then
  echo "未找到 pytest 可执行文件: $PYTEST_BIN"
  echo "可执行: $PYTHON_BIN -m pip install -r $ROOT_DIR/requirements.txt pytest"
  exit 1
fi

echo "[1/4] 运行分布式计算单元测试 + API 集成测试"
"$PYTEST_BIN" \
  "$ROOT_DIR/services/backend/tests/test_distributed_compute_service.py" \
  "$ROOT_DIR/services/backend/tests/test_distributed_compute_api.py" \
  -q

if [[ "$FULL_BACKEND" -eq 1 ]]; then
  echo "[2/4] 运行完整后端单元测试套件"
  "$PYTEST_BIN" "$ROOT_DIR/services/backend/tests" -q
else
  echo "[2/4] 跳过完整后端单元测试套件（可加 --full-backend 开启）"
fi

if [[ "$SKIP_BENCHMARK" -eq 0 ]]; then
  echo "[3/4] 运行分布式计算性能基准"
  "$PYTHON_BIN" "$ROOT_DIR/services/backend/tests/performance/benchmark_distributed_compute.py" \
    --tasks 20 \
    --values-per-task 3000 \
    --chunk-size 96 \
    --json-out "$ROOT_DIR/reports/distributed_compute_benchmark.json"
else
  echo "[3/4] 跳过性能基准"
fi

echo "[4/4] 输出压力测试建议命令"
cat <<'CMD'
可在本地启动后端后执行压力测试:
  locust -f services/backend/tests/performance/locust_distributed_compute.py \
    --host http://127.0.0.1:8000
CMD

echo "分布式计算测试流程完成"
