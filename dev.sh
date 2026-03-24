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

# 检查端口是否被占用
check_port() {
    local port=$1
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        return 0  # 端口被占用
    else
        return 1  # 端口可用
    fi
}

# 清理占用端口的进程
cleanup_port() {
    local port=$1
    log_info "清理端口 $port 的占用进程..."
    
    local pids=$(lsof -ti :$port 2>/dev/null || true)
    if [ ! -z "$pids" ]; then
        log_warning "端口 $port 被以下进程占用: $pids"
        echo "$pids" | xargs kill -9 2>/dev/null || true
        sleep 1
        
        # 再次检查
        if check_port $port; then
            log_error "无法清理端口 $port，请手动处理"
            return 1
        else
            log_success "端口 $port 已清理"
        fi
    fi
    return 0
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
    
    # 检查后端端口
    if check_port 8000; then
        log_warning "后端端口 8000 已被占用"
        read -p "是否自动清理端口占用？(y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            cleanup_port 8000
        else
            log_error "请手动清理端口 8000 后重试"
            exit 1
        fi
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
    
    # 检查后端启动脚本（优先新目录，兼容旧目录）
    local backend_dir=""
    if [ -f "services/backend/run.py" ]; then
        backend_dir="services/backend"
    elif [ -f "backend/run.py" ]; then
        backend_dir="backend"
    fi

    if [ -n "$backend_dir" ]; then
        cd "$backend_dir"
        
        # 激活虚拟环境并启动后端
        if [ -f "../venv/bin/activate" ]; then
            source ../venv/bin/activate
        fi
        
        python3 run.py > /tmp/udake_backend.log 2>&1 &
        BACKEND_PID=$!
        cd "$PROJECT_ROOT"
        
        log_success "后端服务已启动 (PID: $BACKEND_PID)"
        
        # 等待后端启动并检查状态
        log_info "等待后端服务就绪..."
        local max_wait=30
        local wait_count=0
        
        while [ $wait_count -lt $max_wait ]; do
            if ! ps -p $BACKEND_PID > /dev/null; then
                log_error "后端服务启动失败，查看日志: /tmp/udake_backend.log"
                echo ""
                echo "=== 错误日志 ==="
                tail -30 /tmp/udake_backend.log
                echo "================"
                exit 1
            fi
            
            # 检查端口是否开始监听
            if check_port 8000; then
                # 检查API是否真的可用（测试/industries接口）
                if curl -s http://172.20.10.2:8000/api/industries > /dev/null 2>&1; then
                    echo ""
                    log_success "后端服务就绪，API接口正常响应"
                    return 0
                else
                    # 端口已监听但API还没准备好
                    log_info "API接口尚未就绪，继续等待..."
                fi
            fi
            
            sleep 1
            wait_count=$((wait_count + 1))
            echo -n "."
        done
        
        echo ""
        log_error "后端服务启动超时，无法访问API接口"
        log_error "查看日志: /tmp/udake_backend.log"
        echo ""
        echo "=== 错误日志 ==="
        tail -30 /tmp/udake_backend.log
        echo "================"
        exit 1
        
    else
        log_warning "未找到后端启动脚本（services/backend/run.py 或 backend/run.py），跳过后端启动"
    fi
}

# 启动前端开发服务器
start_frontend() {
    log_info "启动前端开发服务器..."
    
    npm run dev > /tmp/udake_frontend.log 2>&1 &
    FRONTEND_PID=$!
    
    log_success "前端服务已启动 (PID: $FRONTEND_PID)"
    
    # 等待前端服务启动并检查状态
    log_info "等待前端服务就绪..."
    local max_wait=15
    local wait_count=0
    
    while [ $wait_count -lt $max_wait ]; do
        if ! ps -p $FRONTEND_PID > /dev/null; then
            log_error "前端服务启动失败，查看日志: /tmp/udake_frontend.log"
            echo ""
            echo "=== 错误日志 ==="
            tail -20 /tmp/udake_frontend.log
            echo "================"
            exit 1
        fi
        
        # 检查前端服务是否可以访问
        if curl -s http://172.20.10.2:5173 > /dev/null 2>&1; then
            log_success "前端服务就绪"
            return 0
        fi
        
        sleep 1
        wait_count=$((wait_count + 1))
        echo -n "."
    done
    
    echo ""
    log_warning "前端服务启动时间较长，继续启动 Electron..."
}

# 启动 Electron 开发模式
start_electron() {
    log_info "启动 Electron 开发模式..."
    
    # 检查 Electron 主进程文件
    if [ ! -f "apps/electron/main.js" ]; then
        log_error "未找到 Electron 主进程文件: apps/electron/main.js"
        exit 1
    fi
    
    # 检查前端构建产物
    if [ ! -d "apps/frontend/dist" ]; then
        log_warning "未找到前端构建产物，构建中..."
        npm run build:prod
    fi
    
    # 启动 Electron
    npx electron . > /tmp/udake_electron.log 2>&1 &
    ELECTRON_PID=$!
    
    log_success "Electron 应用已启动 (PID: $ELECTRON_PID)"
    
    # 等待 Electron 启动
    sleep 3
    
    # 检查 Electron 是否正常运行
    if ! ps -p $ELECTRON_PID > /dev/null; then
        log_error "Electron 启动失败，查看日志: /tmp/udake_electron.log"
        echo ""
        echo "=== 错误日志 ==="
        tail -20 /tmp/udake_electron.log
        echo "================"
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

# 健康检查
health_check() {
    local healthy=true
    
    if [ ! -z "$BACKEND_PID" ]; then
        if ps -p $BACKEND_PID > /dev/null; then
            # 检查后端进程和API可用性
            if check_port 8000 && curl -s http://172.20.10.2:8000/api/industries > /dev/null 2>&1; then
                echo -e "${GREEN}✓${NC} 后端服务 (PID: $BACKEND_PID, API正常)"
            else
                echo -e "${YELLOW}⚠${NC} 后端服务运行中但API异常 (PID: $BACKEND_PID)"
                healthy=false
            fi
        else
            echo -e "${RED}✗${NC} 后端服务已停止"
            healthy=false
        fi
    fi
    
    if [ ! -z "$FRONTEND_PID" ]; then
        if ps -p $FRONTEND_PID > /dev/null; then
            echo -e "${GREEN}✓${NC} 前端服务 (PID: $FRONTEND_PID)"
        else
            echo -e "${RED}✗${NC} 前端服务已停止"
            healthy=false
        fi
    fi
    
    if [ ! -z "$ELECTRON_PID" ]; then
        if ps -p $ELECTRON_PID > /dev/null; then
            echo -e "${GREEN}✓${NC} Electron 应用 (PID: $ELECTRON_PID)"
        else
            echo -e "${RED}✗${NC} Electron 应用已停止"
            healthy=false
        fi
    fi
    
    return $([ "$healthy" = true ] && echo 0 || echo 1)
}

# 主函数
main() {
    echo ""
    log_info "UDAKE Electron 开发模式启动"
    echo ""
    
    # 检查依赖
    check_dependencies
    
    # 启动服务（确保后端就绪后再启动前端）
    log_info "启动服务流程..."
    if start_backend; then
        log_success "后端服务启动成功，继续启动前端"
        start_frontend
        start_electron
    else
        log_error "后端服务启动失败，停止启动流程"
        exit 1
    fi
    
    # 显示信息
    show_info
    
    log_success "所有服务已启动，开发模式运行中..."
    echo ""
    
    # 定期健康检查
    log_info "启动健康检查监控..."
    while true; do
        sleep 30
        echo ""
        echo "=== 健康检查 $(date '+%H:%M:%S') ==="
        health_check || log_warning "部分服务异常，请检查日志"
        echo "=========================="
    done
}

# 执行主函数
main "$@"
