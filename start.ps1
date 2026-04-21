# SmartLink 快捷启动脚本 (PowerShell)
# 用法: .\start.ps1 [命令]

param(
    [Parameter(Position=0)]
    [string]$Command = "help"
)

# 颜色函数
function Write-ColorOutput {
    param([string]$Message, [string]$Color = "White")
    Write-Host $Message -ForegroundColor $Color
}

# 打印帮助
function Print-Help {
    Write-ColorOutput "SmartLink 快捷启动脚本" "Cyan"
    Write-Host ""
    Write-Host "用法: .\start.ps1 [命令]"
    Write-Host ""
    Write-Host "可用命令:"
    Write-ColorOutput "  dev        - 启动开发服务器 (热重载)" "Green"
    Write-ColorOutput "  prod       - 启动生产服务器 (多进程)" "Green"
    Write-ColorOutput "  init       - 初始化数据库" "Green"
    Write-ColorOutput "  test       - 运行测试" "Green"
    Write-ColorOutput "  lint       - 代码格式化 + 类型检查" "Green"
    Write-ColorOutput "  clean      - 清理缓存和临时文件" "Green"
    Write-ColorOutput "  status     - 查看服务状态" "Green"
    Write-ColorOutput "  docker     - Docker Compose 启动" "Green"
    Write-ColorOutput "  help       - 显示此帮助信息" "Green"
    Write-Host ""
    Write-Host "示例:"
    Write-Host "  .\start.ps1 dev      # 启动开发服务器"
    Write-Host "  .\start.ps1 init     # 初始化数据库"
}

# 启动开发服务器
function Start-Dev {
    Write-ColorOutput "[DEV] 启动开发服务器..." "Green"
    uvicorn gateway.main:app --reload --host 0.0.0.0 --port 8000
}

# 启动生产服务器
function Start-Prod {
    Write-ColorOutput "[PROD] 启动生产服务器..." "Green"
    gunicorn gateway.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --timeout 30 --keep-alive 5 --log-level info
}

# 初始化数据库
function Init-Database {
    Write-ColorOutput "[INIT] 初始化数据库..." "Yellow"
    python scripts/init_db.py
    Write-ColorOutput "[OK] 数据库初始化完成" "Green"
}

# 运行测试
function Run-Tests {
    Write-ColorOutput "[TEST] 运行测试..." "Cyan"
    pytest --cov=. tests/ -v
}

# 代码检查
function Run-Lint {
    Write-ColorOutput "[LINT] 代码格式化..." "Cyan"
    black . --line-length 100
    isort . --line-length 100 --profile black
    Write-ColorOutput "[TYPE] 类型检查..." "Cyan"
    mypy . --ignore-missing-imports
    Write-ColorOutput "[OK] 代码检查完成" "Green"
}

# 清理缓存
function Clean-Cache {
    Write-ColorOutput "[CLEAN] 清理缓存..." "Yellow"
    
    # 删除缓存目录
    $cacheDirs = @(".cache", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache")
    foreach ($dir in $cacheDirs) {
        if (Test-Path $dir) {
            Remove-Item -Path $dir -Recurse -Force -ErrorAction SilentlyContinue
        }
    }
    
    # 删除所有子目录中的 __pycache__
    Get-ChildItem -Path . -Directory -Recurse -Filter "__pycache__" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    
    # 删除 egg-info
    Get-ChildItem -Path . -Directory -Filter "*.egg-info" | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    
    Write-ColorOutput "[OK] 缓存清理完成" "Green"
}

# 查看状态
function Check-Status {
    Write-ColorOutput "[STATUS] 检查服务状态..." "Cyan"
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:8000/health" -ErrorAction Stop
        $response | ConvertTo-Json -Depth 10
    } catch {
        Write-ColorOutput "服务未运行" "Red"
    }
}

# Docker 启动
function Start-Docker {
    Write-ColorOutput "[DOCKER] 启动 Docker Compose..." "Green"
    Push-Location docker
    docker-compose up -d
    Pop-Location
    Write-ColorOutput "[OK] Docker 服务启动完成" "Green"
    docker-compose ps
}

# 快速启动（开发 + 初始化）
function Quick-Start {
    Write-ColorOutput "[QUICK] 快速启动..." "Green"
    
    # 检查数据库是否存在
    if (-not (Test-Path "smartlink.db")) {
        Write-ColorOutput "[INIT] 数据库不存在，正在初始化..." "Yellow"
        python scripts/init_db.py
    }
    
    Write-ColorOutput "[DEV] 启动开发服务器..." "Green"
    uvicorn gateway.main:app --reload --host 0.0.0.0 --port 8000
}

# 安装依赖
function Install-Dependencies {
    Write-ColorOutput "[INSTALL] 安装依赖..." "Yellow"
    pip install -e ".[dev]"
    Write-ColorOutput "[OK] 依赖安装完成" "Green"
}

# 主逻辑
switch ($Command) {
    "dev" { Start-Dev }
    "prod" { Start-Prod }
    "init" { Init-Database }
    "test" { Run-Tests }
    "lint" { Run-Lint }
    "clean" { Clean-Cache }
    "status" { Check-Status }
    "docker" { Start-Docker }
    "quick" { Quick-Start }
    "install" { Install-Dependencies }
    "help" { Print-Help }
    "--help" { Print-Help }
    "-h" { Print-Help }
    default {
        if ($Command -ne "") {
            Write-ColorOutput "未知命令: $Command" "Red"
        }
        Print-Help
    }
}