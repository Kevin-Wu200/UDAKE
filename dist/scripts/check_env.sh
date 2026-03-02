#!/bin/bash

# 检查构建环境脚本

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  UDAKE 构建环境检查"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# 检查 Node.js
echo -n "检查 Node.js... "
if command -v node &> /dev/null; then
    NODE_VERSION=$(node --version)
    echo "✓ $NODE_VERSION"
else
    echo "✗ 未安装"
    echo "请安装 Node.js: https://nodejs.org/"
    exit 1
fi

# 检查 npm
echo -n "检查 npm... "
if command -v npm &> /dev/null; then
    NPM_VERSION=$(npm --version)
    echo "✓ v$NPM_VERSION"
else
    echo "✗ 未安装"
    exit 1
fi

# 检查 Python
echo -n "检查 Python 3... "
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo "✓ $PYTHON_VERSION"
else
    echo "✗ 未安装"
    echo "请安装 Python 3: https://www.python.org/"
    exit 1
fi

# 检查 pip
echo -n "检查 pip3... "
if command -v pip3 &> /dev/null; then
    PIP_VERSION=$(pip3 --version | awk '{print $2}')
    echo "✓ v$PIP_VERSION"
else
    echo "✗ 未安装"
    exit 1
fi

# 检查 iconutil
echo -n "检查 iconutil... "
if command -v iconutil &> /dev/null; then
    echo "✓ 已安装"
else
    echo "✗ 未安装"
    echo "请安装 Xcode Command Line Tools: xcode-select --install"
    exit 1
fi

# 检查 sips
echo -n "检查 sips... "
if command -v sips &> /dev/null; then
    echo "✓ 已安装"
else
    echo "✗ 未安装"
    exit 1
fi

# 检查图标文件
echo -n "检查图标文件... "
if [ -f ".claude/logo.png" ]; then
    echo "✓ 存在"
else
    echo "✗ 不存在"
    echo "请确保 .claude/logo.png 文件存在"
    exit 1
fi

# 检查前端目录
echo -n "检查前端目录... "
if [ -d "frontend" ]; then
    echo "✓ 存在"
else
    echo "✗ 不存在"
    exit 1
fi

# 检查后端目录
echo -n "检查后端目录... "
if [ -d "backend" ]; then
    echo "✓ 存在"
else
    echo "✗ 不存在"
    exit 1
fi

# 检查 dist 目录
echo -n "检查 dist 目录... "
if [ -d "dist" ]; then
    echo "✓ 存在"
else
    echo "✗ 不存在"
    echo "正在创建..."
    mkdir -p dist/build dist/scripts dist/config dist/resources dist/logs dist/tmp dist/release
    echo "✓ 已创建"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  环境检查完成！"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "可以开始构建："
echo "  bash dist/scripts/build_macos.sh"
echo ""
