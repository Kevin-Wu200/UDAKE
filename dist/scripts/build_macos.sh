#!/bin/bash

set -e

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  UDAKE macOS 应用构建脚本${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# 获取项目根目录
PROJECT_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DIST_DIR="$PROJECT_ROOT/dist"
BUILD_DIR="$DIST_DIR/build"
RELEASE_DIR="$DIST_DIR/release"
SCRIPTS_DIR="$DIST_DIR/scripts"
RESOURCES_DIR="$DIST_DIR/resources"
LOGS_DIR="$DIST_DIR/logs"

echo -e "${YELLOW}项目根目录: $PROJECT_ROOT${NC}"
echo -e "${YELLOW}构建目录: $BUILD_DIR${NC}"

# 清理旧的构建产物
echo -e "\n${YELLOW}[1/6] 清理旧的构建产物...${NC}"
rm -rf "$BUILD_DIR"/*
rm -rf "$RELEASE_DIR"/*
mkdir -p "$BUILD_DIR/frontend"
mkdir -p "$BUILD_DIR/backend"
mkdir -p "$RELEASE_DIR"
mkdir -p "$LOGS_DIR"

# 构建前端
echo -e "\n${YELLOW}[2/6] 构建前端...${NC}"
if [ -d "$PROJECT_ROOT/frontend" ]; then
  cp -r "$PROJECT_ROOT/frontend"/* "$BUILD_DIR/frontend/"
  echo -e "${GREEN}✓ 前端文件已复制${NC}"
else
  echo -e "${RED}✗ 前端目录不存在${NC}"
  exit 1
fi

# 构建后端
echo -e "\n${YELLOW}[3/6] 构建后端...${NC}"
if [ -d "$PROJECT_ROOT/backend" ]; then
  # 复制后端代码
  cp -r "$PROJECT_ROOT/backend"/* "$BUILD_DIR/backend/"

  # 检查并安装依赖
  if [ -f "$PROJECT_ROOT/requirements.txt" ]; then
    echo -e "${YELLOW}检查 Python 依赖...${NC}"
    pip3 list > /dev/null 2>&1 || {
      echo -e "${RED}✗ pip3 未安装${NC}"
      exit 1
    }
    echo -e "${GREEN}✓ Python 环境正常${NC}"
  fi

  echo -e "${GREEN}✓ 后端文件已复制${NC}"
else
  echo -e "${RED}✗ 后端目录不存在${NC}"
  exit 1
fi

# 生成应用图标
echo -e "\n${YELLOW}[4/6] 生成应用图标...${NC}"

LOGO_PATH="$PROJECT_ROOT/.claude/logo.png"
ICONSET_DIR="$DIST_DIR/tmp/UDAKE.iconset"
ICNS_PATH="$DIST_DIR/UDAKE.icns"

if [ ! -f "$LOGO_PATH" ]; then
  echo -e "${RED}✗ 图标源文件不存在: $LOGO_PATH${NC}"
  exit 1
fi

# 创建 iconset 目录
rm -rf "$ICONSET_DIR"
mkdir -p "$ICONSET_DIR"

# 生成各种尺寸的图标
echo -e "${YELLOW}生成多尺寸图标...${NC}"
sips -z 16 16     "$LOGO_PATH" --out "$ICONSET_DIR/icon_16x16.png" > /dev/null 2>&1
sips -z 32 32     "$LOGO_PATH" --out "$ICONSET_DIR/icon_16x16@2x.png" > /dev/null 2>&1
sips -z 32 32     "$LOGO_PATH" --out "$ICONSET_DIR/icon_32x32.png" > /dev/null 2>&1
sips -z 64 64     "$LOGO_PATH" --out "$ICONSET_DIR/icon_32x32@2x.png" > /dev/null 2>&1
sips -z 128 128   "$LOGO_PATH" --out "$ICONSET_DIR/icon_128x128.png" > /dev/null 2>&1
sips -z 256 256   "$LOGO_PATH" --out "$ICONSET_DIR/icon_128x128@2x.png" > /dev/null 2>&1
sips -z 256 256   "$LOGO_PATH" --out "$ICONSET_DIR/icon_256x256.png" > /dev/null 2>&1
sips -z 512 512   "$LOGO_PATH" --out "$ICONSET_DIR/icon_256x256@2x.png" > /dev/null 2>&1
sips -z 512 512   "$LOGO_PATH" --out "$ICONSET_DIR/icon_512x512.png" > /dev/null 2>&1
sips -z 1024 1024 "$LOGO_PATH" --out "$ICONSET_DIR/icon_512x512@2x.png" > /dev/null 2>&1

# 转换为 icns
echo -e "${YELLOW}转换为 .icns 格式...${NC}"
iconutil -c icns "$ICONSET_DIR" -o "$ICNS_PATH"

if [ -f "$ICNS_PATH" ]; then
  echo -e "${GREEN}✓ 图标生成成功: $ICNS_PATH${NC}"
  # 清理临时文件
  rm -rf "$ICONSET_DIR"
else
  echo -e "${RED}✗ 图标生成失败${NC}"
  exit 1
fi

# 安装 Electron 依赖
echo -e "\n${YELLOW}[5/6] 安装 Electron 依赖...${NC}"
cd "$DIST_DIR"

if [ ! -f "package.json" ]; then
  echo -e "${RED}✗ package.json 不存在${NC}"
  exit 1
fi

# 检查 npm
if ! command -v npm &> /dev/null; then
  echo -e "${RED}✗ npm 未安装，请先安装 Node.js${NC}"
  exit 1
fi

# 配置代理（如果需要）
if [ -n "$HTTP_PROXY" ] || [ -n "$HTTPS_PROXY" ]; then
  echo -e "${YELLOW}检测到代理设置${NC}"
  [ -n "$HTTP_PROXY" ] && echo -e "  HTTP_PROXY: $HTTP_PROXY"
  [ -n "$HTTPS_PROXY" ] && echo -e "  HTTPS_PROXY: $HTTPS_PROXY"
fi

echo -e "${YELLOW}安装依赖包...${NC}"
npm install --silent

# 构建 Electron 应用
echo -e "\n${YELLOW}[6/6] 构建 Electron 应用...${NC}"
npm run build:mac

# 检查构建结果
if [ -d "$RELEASE_DIR/mac" ]; then
  # 查找生成的 .app
  APP_PATH=$(find "$RELEASE_DIR/mac" -name "*.app" -type d | head -n 1)

  if [ -n "$APP_PATH" ]; then
    # 移动到 release 根目录
    mv "$APP_PATH" "$RELEASE_DIR/UDAKE.app"

    # 清理 mac 子目录
    rm -rf "$RELEASE_DIR/mac"

    echo -e "${GREEN}✓ 应用构建成功: $RELEASE_DIR/UDAKE.app${NC}"
  else
    echo -e "${RED}✗ 未找到生成的 .app 文件${NC}"
    exit 1
  fi
else
  echo -e "${RED}✗ 构建失败${NC}"
  exit 1
fi

# 生成构建信息
echo -e "\n${YELLOW}生成构建信息...${NC}"
BUILD_INFO="$RELEASE_DIR/build_info.json"
cat > "$BUILD_INFO" << EOF
{
  "app_name": "UDAKE",
  "version": "1.0.0",
  "build_date": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "platform": "macOS",
  "architecture": "universal",
  "minimum_os": "12.0",
  "bundle_id": "com.udake.kriging"
}
EOF

echo -e "${GREEN}✓ 构建信息已生成${NC}"

# 完成
echo -e "\n${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}  构建完成！${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "\n应用位置: ${GREEN}$RELEASE_DIR/UDAKE.app${NC}"
echo -e "图标文件: ${GREEN}$ICNS_PATH${NC}"
echo -e "构建信息: ${GREEN}$BUILD_INFO${NC}"
echo -e "\n运行应用:"
echo -e "  ${YELLOW}open \"$RELEASE_DIR/UDAKE.app\"${NC}"
echo -e "\n或直接双击 UDAKE.app 启动\n"
