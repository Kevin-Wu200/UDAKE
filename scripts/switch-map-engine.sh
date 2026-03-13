#!/bin/bash

# 地图引擎切换脚本
# 用于快速切换 UDAKE 的地图引擎

CONFIG_FILE="frontend/js/config/map.config.js"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 显示当前配置
show_current() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}   UDAKE 地图引擎配置${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

    if [ ! -f "$CONFIG_FILE" ]; then
        echo -e "${RED}❌ 配置文件不存在: $CONFIG_FILE${NC}"
        exit 1
    fi

    current=$(grep "MAP_PROVIDER:" "$CONFIG_FILE" | sed "s/.*'\(.*\)'.*/\1/")

    echo -e "\n📍 当前地图引擎: ${GREEN}$current${NC}\n"
}

# 切换到 ArcGIS
switch_to_arcgis() {
    echo -e "${YELLOW}🔄 正在切换到 ArcGIS 模式...${NC}"

    sed -i.bak "s/MAP_PROVIDER: '[^']*'/MAP_PROVIDER: 'arcgis'/" "$CONFIG_FILE"

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ 已切换到 ArcGIS 模式${NC}"
        echo -e "${YELLOW}⚠️  请重启应用以使更改生效${NC}"
    else
        echo -e "${RED}❌ 切换失败${NC}"
        exit 1
    fi
}

# 切换到天地图
switch_to_amap() {
    echo -e "${YELLOW}🔄 正在切换到AMap模式...${NC}"

    sed -i.bak "s/MAP_PROVIDER: '[^']*'/MAP_PROVIDER: 'amap'/" "$CONFIG_FILE"

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ 已切换到AMap模式${NC}"
        echo -e "${YELLOW}⚠️  请重启应用以使更改生效${NC}"
    else
        echo -e "${RED}❌ 切换失败${NC}"
        exit 1
    fi
}

# 显示帮助
show_help() {
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BLUE}   UDAKE 地图引擎切换工具${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
    echo "用法: $0 [选项]"
    echo ""
    echo "选项:"
    echo "  arcgis      切换到 ArcGIS 模式"
    echo "  amap    切换到天地图模式"
    echo "  status      显示当前配置"
    echo "  help        显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  $0 arcgis       # 切换到 ArcGIS"
    echo "  $0 amap     # 切换到天地图"
    echo "  $0 status       # 查看当前配置"
    echo ""
}

# 主逻辑
case "$1" in
    arcgis)
        show_current
        switch_to_arcgis
        ;;
    amap)
        show_current
        switch_to_amap
        ;;
    status)
        show_current
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        show_help
        exit 1
        ;;
esac

echo ""
