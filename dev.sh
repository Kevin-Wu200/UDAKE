#!/bin/bash

# UDAKE Electron 开发者测试脚本
# 用于启动 Electron 应用的开发模式

set -e  # 遇到错误立即退出

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_ROOT"

# 日志函数
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# 检查依赖
check_dependencies() {
    log_info "检查依赖环境..."
    
    # 检查 Node.js
    if ! command -v node &> /dev/null; then
        log_error "未找到 Node.js，请先安装 Node.js"
        exit 1
    fi
    
    # 检查 npm
    if ! command -v npm &> /dev/null; then
        log_error "未找到 npm，请先安装 npm"
        exit 1
    fi
    
    # 检查 node_modules
    if [ ! -d "node_modules" ]; then
        log_warning "未找到 node_modules，正在安装依赖..."
        npm install
    fi
    
    log_success "依赖检查完成"
}

# 清理函数
cleanup() {
    log_info "清理进程..."
    
    # 杀死后端进程
    if [ ! -z "$BACKEND_PID" ]; then
        kill $BACKEND_PID 2>/dev/null || true
    fi
    
    # 杀死前端进程
    if [ ! -z "$FRONTEND_PID" ]; then
        kill $FRONTEND_PID 2>/dev/null || true
    fi
    
    # 杀死 Electron 进程
    if [ ! -z "$ELECTRON_PID" ]; then
        kill $ELECTRON_PID 2>/dev/null || true
    fi
    
    # 清理所有相关进程
    pkill -f "vite" 2>/dev/null || true
    pkill -f "electron" 2>/dev/null || true
    pkill -f "python.*run.py" 2>/dev/null || true
    
    log_success "清理完成"
}

# 捕获退出信号
trap cleanup EXIT INT TERM

# 启动后端服务
start_backend() {
    log_info "启动后端服务..."
    
    # 检查虚拟环境
    if [ ! -d "venv" ]; then
        log_warning "未找到虚拟环境，跳过后端启动"
        return
    fi
    
    # 检查后端启动脚本
    if [ -f "backend/run.py" ]; then
        cd backend
        python3 run.py > /tmp/udake_backend.log 2>&1 &
        BACKEND_PID=$!
        cd ..
        log_success "后端服务已启动 (PID: $BACKEND_PID)"
        
        # 等待后端启动
        sleep 2
        
        # 检查后端是否正常运行
        if ! ps -p $BACKEND_PID > /dev/null; then
            log_error "后端服务启动失败，查看日志: /tmp/udake_backend.log"
            cat /tmp/udake_backend.log
            exit 1
        fi
    else
        log_warning "未找到后端启动脚本，跳过后端启动"
    fi
}

# 启动前端开发服务器
start_frontend() {
    log_info "启动前端开发服务器..."
    
    npm run dev > /tmp/udake_frontend.log 2>&1 &
    FRONTEND_PID=$!
    
    log_success "前端服务已启动 (PID: $FRONTEND_PID)"
    
    # 等待前端服务启动
    sleep 3
    
    # 检查前端服务是否正常运行
    if ! ps -p $FRONTEND_PID > /dev/null; then
        log_error "前端服务启动失败，查看日志: /tmp/udake_frontend.log"
        cat /tmp/udake_frontend.log
        exit 1
    fi
}

# 启动 Electron 开发模式
start_electron() {
    log_info "启动 Electron 开发模式..."
    
    # 检查 Electron 主进程文件
    if [ ! -f "electron/main.js" ]; then
        log_error "未找到 Electron 主进程文件: electron/main.js"
        exit 1
    fi
    
    # 启动 Electron
    npx electron . > /tmp/udake_electron.log 2>&1 &
    ELECTRON_PID=$!
    
    log_success "Electron 应用已启动 (PID: $ELECTRON_PID)"
    
    # 等待 Electron 启动
    sleep 2
    
    # 检查 Electron 是否正常运行
    if ! ps -p $ELECTRON_PID > /dev/null; then
        log_error "Electron 启动失败，查看日志: /tmp/udake_electron.log"
        cat /tmp/udake_electron.log
        exit 1
    fi
}

# 显示运行信息
show_info() {
    echo ""
    echo "==================================="
    echo "  UDAKE Electron 开发模式"
    echo "==================================="
    echo ""
    echo "服务信息:"
    echo "  - 后端 PID: ${BACKEND_PID:-未启动}"
    echo "  - 前端 PID: $FRONTEND_PID"
    echo "  - Electron PID: $ELECTRON_PID"
    echo ""
    echo "日志文件:"
    echo "  - 后端: /tmp/udake_backend.log"
    echo "  - 前端: /tmp/udake_frontend.log"
    echo "  - Electron: /tmp/udake_electron.log"
    echo ""
    echo "按 Ctrl+C 停止所有服务"
    echo "==================================="
    echo ""
}

# 主函数
main() {
    echo ""
    log_info "UDAKE Electron 开发模式启动"
    echo ""
    
    # 检查依赖
    check_dependencies
    
    # 启动服务
    start_backend
    start_frontend
    start_electron
    
    # 显示信息
    show_info
    
    log_success "所有服务已启动，开发模式运行中..."
    echo ""
    
    # 保持脚本运行
    wait
}

# 执行主函数
main "$@"