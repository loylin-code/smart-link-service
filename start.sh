#!/usr/bin/env bash
# SmartLink 快捷启动脚本
# 用法: ./start.sh [命令]

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印帮助
print_help() {
    echo -e "${BLUE}SmartLink 快捷启动脚本${NC}"
    echo ""
    echo "用法: ./start.sh [命令]"
    echo ""
    echo "可用命令:"
    echo -e "  ${GREEN}dev${NC}        - 启动开发服务器 (热重载)"
    echo -e "  ${GREEN}prod${NC}       - 启动生产服务器 (多进程)"
    echo -e "  ${GREEN}init${NC}       - 初始化数据库"
    echo -e "  ${GREEN}test${NC}       - 运行测试"
    echo -e "  ${GREEN}lint${NC}       - 代码格式化 + 类型检查"
    echo -e "  ${GREEN}clean${NC}      - 清理缓存和临时文件"
    echo -e "  ${GREEN}status${NC}     - 查看服务状态"
    echo -e "  ${GREEN}logs${NC}       - 查看日志"
    echo -e "  ${GREEN}docker${NC}     - Docker Compose 启动"
    echo -e "  ${GREEN}help${NC}       - 显示此帮助信息"
    echo ""
    echo "示例:"
    echo "  ./start.sh dev      # 启动开发服务器"
    echo "  ./start.sh init     # 初始化数据库"
}

# 启动开发服务器
start_dev() {
    echo -e "${GREEN}[DEV] 启动开发服务器...${NC}"
    uvicorn gateway.main:app --reload --host 0.0.0.0 --port 8000
}

# 启动生产服务器
start_prod() {
    echo -e "${GREEN}[PROD] 启动生产服务器...${NC}"
    gunicorn gateway.main:app \
        --workers 4 \
        --worker-class uvicorn.workers.UvicornWorker \
        --bind 0.0.0.0:8000 \
        --timeout 30 \
        --keep-alive 5 \
        --log-level info
}

# 初始化数据库
init_db() {
    echo -e "${YELLOW}[INIT] 初始化数据库...${NC}"
    python scripts/init_db.py
    echo -e "${GREEN}[OK] 数据库初始化完成${NC}"
}

# 运行测试
run_tests() {
    echo -e "${BLUE}[TEST] 运行测试...${NC}"
    pytest --cov=. tests/ -v
}

# 代码检查
run_lint() {
    echo -e "${BLUE}[LINT] 代码格式化...${NC}"
    black . --line-length 100
    isort . --line-length 100 --profile black
    echo -e "${BLUE}[TYPE] 类型检查...${NC}"
    mypy . --ignore-missing-imports
    echo -e "${GREEN}[OK] 代码检查完成${NC}"
}

# 清理缓存
clean_cache() {
    echo -e "${YELLOW}[CLEAN] 清理缓存...${NC}"
    rm -rf .cache
    rm -rf __pycache__
    rm -rf .pytest_cache
    rm -rf .mypy_cache
    rm -rf *.egg-info
    rm -rf .ruff_cache
    find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
    echo -e "${GREEN}[OK] 缓存清理完成${NC}"
}

# 查看状态
check_status() {
    echo -e "${BLUE}[STATUS] 检查服务状态...${NC}"
    curl -s http://localhost:8000/health | python -m json.tool || echo -e "${RED}服务未运行${NC}"
}

# 查看日志
view_logs() {
    echo -e "${BLUE}[LOGS] 查看日志...${NC}"
    if [ -f "logs/app.log" ]; then
        tail -f logs/app.log
    else
        echo -e "${YELLOW}日志文件不存在，使用标准输出${NC}"
    fi
}

# Docker 启动
start_docker() {
    echo -e "${GREEN}[DOCKER] 启动 Docker Compose...${NC}"
    cd docker
    docker-compose up -d
    cd ..
    echo -e "${GREEN}[OK] Docker 服务启动完成${NC}"
    docker-compose ps
}

# 主逻辑
case "$1" in
    dev)
        start_dev
        ;;
    prod)
        start_prod
        ;;
    init)
        init_db
        ;;
    test)
        run_tests
        ;;
    lint)
        run_lint
        ;;
    clean)
        clean_cache
        ;;
    status)
        check_status
        ;;
    logs)
        view_logs
        ;;
    docker)
        start_docker
        ;;
    help|--help|-h)
        print_help
        ;;
    *)
        if [ -z "$1" ]; then
            print_help
        else
            echo -e "${RED}未知命令: $1${NC}"
            print_help
            exit 1
        fi
        ;;
esac