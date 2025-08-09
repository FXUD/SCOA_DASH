#!/bin/bash

# SCOA Dashboard 停止脚本
# 用于停止所有Docker服务

set -e

echo "🛑 Stopping SCOA Crypto Trading Dashboard..."

# 获取脚本所在目录的父目录作为项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "📂 Project directory: $PROJECT_ROOT"

# 停止所有服务
echo "⏹️  Stopping all services..."
docker-compose down

echo ""
echo "✅ SCOA Dashboard stopped successfully!"
echo ""
echo "💡 To remove all data (including databases):"
echo "   docker-compose down -v"
echo ""
echo "🔄 To restart:"
echo "   ./scripts/start.sh"