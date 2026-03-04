@echo off
REM SmartLink Development Startup Script for Windows
REM This script starts all services for local development

echo 🚀 Starting SmartLink Development Environment...

REM Check if Docker is running
docker info >nul 2>&1
if errorlevel 1 (
    echo ❌ Docker is not running. Please start Docker first.
    exit /b 1
)

REM Change to docker directory
cd /d %~dp0

REM Stop any existing containers
echo 🛑 Stopping existing containers...
docker-compose down

REM Start services
echo 📦 Starting services...
docker-compose up -d postgres redis minio

REM Wait for services to be healthy
echo ⏳ Waiting for services to be ready...
timeout /t 5 /nobreak >nul

REM Check if database is ready
:check_postgres
docker-compose exec -T postgres pg_isready -U postgres >nul 2>&1
if errorlevel 1 (
    echo Waiting for PostgreSQL...
    timeout /t 2 /nobreak >nul
    goto check_postgres
)

echo ✅ PostgreSQL is ready!

REM Check if Redis is ready
:check_redis
docker-compose exec -T redis redis-cli ping | findstr "PONG" >nul
if errorlevel 1 (
    echo Waiting for Redis...
    timeout /t 2 /nobreak >nul
    goto check_redis
)

echo ✅ Redis is ready!

REM Start the API service
echo 🌐 Starting API service...
docker-compose up api

echo ✨ Development environment is running!
echo.
echo Services:
echo   - API: http://localhost:8000
echo   - API Docs: http://localhost:8000/docs
echo   - PostgreSQL: localhost:5432
echo   - Redis: localhost:6379
echo   - MinIO Console: http://localhost:9001
echo.
echo To stop: docker-compose down