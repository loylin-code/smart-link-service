#!/bin/bash

# SmartLink Development Startup Script
# This script starts all services for local development

set -e

echo "🚀 Starting SmartLink Development Environment..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker first."
    exit 1
fi

# Change to docker directory
cd "$(dirname "$0")"

# Stop any existing containers
echo "🛑 Stopping existing containers..."
docker-compose down

# Start services
echo "📦 Starting services..."
docker-compose up -d postgres redis minio

# Wait for services to be healthy
echo "⏳ Waiting for services to be ready..."
sleep 5

# Check if database is ready
until docker-compose exec -T postgres pg_isready -U postgres; do
    echo "Waiting for PostgreSQL..."
    sleep 2
done

echo "✅ PostgreSQL is ready!"

# Check if Redis is ready
until docker-compose exec -T redis redis-cli ping | grep -q PONG; do
    echo "Waiting for Redis..."
    sleep 2
done

echo "✅ Redis is ready!"

# Start the API service
echo "🌐 Starting API service..."
docker-compose up api

echo "✨ Development environment is running!"
echo ""
echo "Services:"
echo "  - API: http://localhost:8000"
echo "  - API Docs: http://localhost:8000/docs"
echo "  - PostgreSQL: localhost:5432"
echo "  - Redis: localhost:6379"
echo "  - MinIO Console: http://localhost:9001"
echo ""
echo "To stop: docker-compose down"