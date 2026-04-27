#!/bin/bash
set -euo pipefail

PROJECT_ROOT="."
VENV_PATH="$PROJECT_ROOT/guming/bin/activate"
BACKEND_DIR="$PROJECT_ROOT/services/backend"

if [ ! -f "$VENV_PATH" ]; then
  echo "错误: 未找到虚拟环境激活脚本: $VENV_PATH" >&2
  exit 1
fi

if [ ! -d "$BACKEND_DIR" ]; then
  echo "错误: 未找到后端目录: $BACKEND_DIR" >&2
  exit 1
fi

# 激活虚拟环境
source "$VENV_PATH"

# 进入后端目录
cd "$BACKEND_DIR"

# 启动服务并透传参数
python run.py "$@"
