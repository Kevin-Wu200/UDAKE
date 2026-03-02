#!/bin/bash

# 设置代理并构建 macOS 应用
# 使用方法: ./build_with_proxy.sh [proxy_url]
# 例如: ./build_with_proxy.sh http://127.0.0.1:7890

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 获取脚本目录
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 代理地址（可以从参数传入，或使用默认值）
PROXY_URL="${1:-http://127.0.0.1:7890}"

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  使用代理构建 UDAKE macOS 应用${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}代理地址: $PROXY_URL${NC}\n"

# 设置代理环境变量
export HTTP_PROXY="$PROXY_URL"
export HTTPS_PROXY="$PROXY_URL"
export http_proxy="$PROXY_URL"
export https_proxy="$PROXY_URL"

# 设置 npm 代理
npm config set proxy "$PROXY_URL"
npm config set https-proxy "$PROXY_URL"

# 设置 Electron 镜像（可选，使用淘宝镜像）
export ELECTRON_MIRROR="https://npmmirror.com/mirrors/electron/"

echo -e "${GREEN}✓ 代理配置完成${NC}\n"

# 运行构建脚本
bash "$SCRIPT_DIR/build_macos.sh"

# 清理 npm 代理配置
npm config delete proxy
npm config delete https-proxy

echo -e "\n${GREEN}✓ 构建完成，代理配置已清理${NC}"
