#!/bin/bash

# 开发模式启动脚本

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  UDAKE 开发模式启动"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DIST_DIR="$PROJECT_ROOT/dist"

# 检查 node_modules
if [ ! -d "$DIST_DIR/node_modules" ]; then
    echo "首次运行，安装 Electron 依赖..."
    cd "$DIST_DIR"
    npm install
    echo ""
fi

# 构建前端项目
echo "构建前端项目..."
cd "$PROJECT_ROOT"
npm run build

# 启动应用
echo "启动 Electron 应用..."
cd "$DIST_DIR"
npm start
