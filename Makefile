# SmartLink Makefile
# 用法: make [命令]

.PHONY: help dev prod init test lint clean status docker install quick

# 默认目标
help:
	@echo "SmartLink 快捷命令"
	@echo ""
	@echo "用法: make [命令]"
	@echo ""
	@echo "可用命令:"
	@echo "  dev      - 启动开发服务器 (热重载)"
	@echo "  prod     - 启动生产服务器 (多进程)"
	@echo "  init     - 初始化数据库"
	@echo "  test     - 运行测试"
	@echo "  lint     - 代码格式化 + 类型检查"
	@echo "  clean    - 清理缓存和临时文件"
	@echo "  status   - 查看服务状态"
	@echo "  docker   - Docker Compose 启动"
	@echo "  install  - 安装依赖"
	@echo "  quick    - 快速启动 (初始化 + 开发服务器)"
	@echo ""

# 开发服务器
dev:
	uvicorn gateway.main:app --reload --host 0.0.0.0 --port 8000

# 生产服务器
prod:
	gunicorn gateway.main:app \
		--workers 4 \
		--worker-class uvicorn.workers.UvicornWorker \
		--bind 0.0.0.0:8000 \
		--timeout 30 \
		--keep-alive 5 \
		--log-level info

# 初始化数据库
init:
	python scripts/init_db.py

# 运行测试
test:
	pytest --cov=. tests/ -v

# 代码检查
lint:
	black . --line-length 100
	isort . --line-length 100 --profile black
	mypy . --ignore-missing-imports

# 清理缓存
clean:
	rm -rf .cache __pycache__ .pytest_cache .mypy_cache .ruff_cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true

# 查看状态
status:
	curl -s http://localhost:8000/health | python -m json.tool || echo "服务未运行"

# Docker 启动
docker:
	cd docker && docker-compose up -d && docker-compose ps

# 安装依赖
install:
	pip install -e ".[dev]"

# 快速启动
quick:
	@if [ ! -f smartlink.db ]; then \
		echo "数据库不存在，正在初始化..."; \
		python scripts/init_db.py; \
	fi
	@echo "启动开发服务器..."
	uvicorn gateway.main:app --reload --host 0.0.0.0 --port 8000

# 数据库迁移
migrate:
	alembic upgrade head

# 创建迁移
makemigration:
	alembic revision --autogenerate -m "$(message)"

# 重置数据库
reset-db:
	rm -f smartlink.db
	python scripts/init_db.py

# 格式化代码
format:
	black . --line-length 100
	isort . --line-length 100 --profile black

# 类型检查
typecheck:
	mypy . --ignore-missing-imports

# 监控日志
logs:
	@if [ -f logs/app.log ]; then \
		tail -f logs/app.log; \
	else \
		echo "日志文件不存在"; \
	fi