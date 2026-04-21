@echo off
REM SmartLink 快捷启动脚本 (Windows Batch)
REM 用法: start.bat [命令]

setlocal

REM 设置颜色
set "GREEN=[92m"
set "YELLOW=[93m"
set "CYAN=[96m"
set "RED=[91m"
set "NC=[0m"

REM 主逻辑
if "%1"=="" goto help
if "%1"=="dev" goto dev
if "%1"=="prod" goto prod
if "%1"=="init" goto init
if "%1"=="test" goto test
if "%1"=="lint" goto lint
if "%1"=="clean" goto clean
if "%1"=="status" goto status
if "%1"=="docker" goto docker
if "%1"=="install" goto install
if "%1"=="quick" goto quick
if "%1"=="help" goto help
if "%1"=="--help" goto help
if "%1"=="-h" goto help

echo %RED%未知命令: %1%NC%
goto help

:help
echo %CYAN%SmartLink 快捷启动脚本%NC%
echo.
echo 用法: start.bat [命令]
echo.
echo 可用命令:
echo %GREEN%  dev        - 启动开发服务器 (热重载)%NC%
echo %GREEN%  prod       - 启动生产服务器 (多进程)%NC%
echo %GREEN%  init       - 初始化数据库%NC%
echo %GREEN%  test       - 运行测试%NC%
echo %GREEN%  lint       - 代码格式化 + 类型检查%NC%
echo %GREEN%  clean      - 清理缓存和临时文件%NC%
echo %GREEN%  status     - 查看服务状态%NC%
echo %GREEN%  docker     - Docker Compose 启动%NC%
echo %GREEN%  install    - 安装依赖%NC%
echo %GREEN%  quick      - 快速启动 (初始化 + 开发服务器)%NC%
echo %GREEN%  help       - 显示此帮助信息%NC%
echo.
echo 示例:
echo   start.bat dev      # 启动开发服务器
echo   start.bat init     # 初始化数据库
goto end

:dev
echo %GREEN%[DEV] 启动开发服务器...%NC%
uvicorn gateway.main:app --reload --host 0.0.0.0 --port 8000
goto end

:prod
echo %GREEN%[PROD] 启动生产服务器...%NC%
gunicorn gateway.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --timeout 30 --keep-alive 5 --log-level info
goto end

:init
echo %YELLOW%[INIT] 初始化数据库...%NC%
python scripts/init_db.py
echo %GREEN%[OK] 数据库初始化完成%NC%
goto end

:test
echo %CYAN%[TEST] 运行测试...%NC%
pytest --cov=. tests/ -v
goto end

:lint
echo %CYAN%[LINT] 代码格式化...%NC%
black . --line-length 100
isort . --line-length 100 --profile black
echo %CYAN%[TYPE] 类型检查...%NC%
mypy . --ignore-missing-imports
echo %GREEN%[OK] 代码检查完成%NC%
goto end

:clean
echo %YELLOW%[CLEAN] 清理缓存...%NC%
if exist .cache rmdir /s /q .cache
if exist __pycache__ rmdir /s /q __pycache__
if exist .pytest_cache rmdir /s /q .pytest_cache
if exist .mypy_cache rmdir /s /q .mypy_cache
if exist .ruff_cache rmdir /s /q .ruff_cache
for /d /r %%d in (__pycache__) do @if exist "%%d" rmdir /s /q "%%d"
echo %GREEN%[OK] 缓存清理完成%NC%
goto end

:status
echo %CYAN%[STATUS] 检查服务状态...%NC%
curl -s http://localhost:8000/health
if errorlevel 1 echo %RED%服务未运行%NC%
goto end

:docker
echo %GREEN%[DOCKER] 启动 Docker Compose...%NC%
cd docker
docker-compose up -d
cd ..
echo %GREEN%[OK] Docker 服务启动完成%NC%
docker-compose ps
goto end

:install
echo %YELLOW%[INSTALL] 安装依赖...%NC%
pip install -e ".[dev]"
echo %GREEN%[OK] 依赖安装完成%NC%
goto end

:quick
echo %GREEN%[QUICK] 快速启动...%NC%
if not exist smartlink.db (
    echo %YELLOW%[INIT] 数据库不存在，正在初始化...%NC%
    python scripts/init_db.py
)
echo %GREEN%[DEV] 启动开发服务器...%NC%
uvicorn gateway.main:app --reload --host 0.0.0.0 --port 8000
goto end

:end
endlocal