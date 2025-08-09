#!/bin/bash

# SCOA Dashboard 启动脚本
# 用于启动整个加密货币交易所监控系统

set -e

echo "🚀 Starting SCOA Crypto Trading Dashboard..."

# 检查Docker和Docker Compose是否安装
if ! command -v docker &> /dev/null; then
    echo "❌ Error: Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Error: Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# 获取脚本所在目录的父目录作为项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "📂 Project directory: $PROJECT_ROOT"

# 检查必需的配置文件
if [ ! -f "config/config.yml" ]; then
    echo "❌ Error: config/config.yml not found."
    echo "📝 Please copy config/config.example.yml to config/config.yml and fill in your API credentials."
    exit 1
fi

# 创建必需的目录
echo "📁 Creating necessary directories..."
mkdir -p logs data/influxdb data/grafana docker/influxdb/config

# 检查配置文件中的API密钥
echo "🔍 Checking configuration..."
if grep -q "your-.*-api-key-here" config/config.yml; then
    echo "⚠️  Warning: Found placeholder API keys in config.yml"
    echo "📝 Please update config/config.yml with your actual API credentials before proceeding."
    echo ""
    echo "To continue anyway (for testing), press Enter. To exit, press Ctrl+C."
    read -r
fi

# 显示启动信息
echo ""
echo "🔧 Starting services with Docker Compose..."
echo "📊 InfluxDB will be available at: http://localhost:8088"
echo "📈 Grafana will be available at: http://localhost:3033"
echo "   - Username: admin"
echo "   - Password: admin123"
echo ""

# 启动Docker服务
docker-compose up -d --build

# 等待服务启动
echo "⏳ Waiting for services to start..."
sleep 10

# 检查服务状态
echo ""
echo "🔍 Checking service status..."
docker-compose ps

# 显示访问信息
echo ""
echo "✅ SCOA Dashboard started successfully!"
echo ""
echo "🌐 Access your dashboards:"
echo "   📈 Grafana: http://localhost:3033"
echo "   📊 InfluxDB: http://localhost:8088"
echo ""
echo "📖 Default Grafana credentials:"
echo "   Username: admin"
echo "   Password: admin123"
echo ""
echo "📝 To view logs: docker-compose logs -f"
echo "🛑 To stop: docker-compose down"
echo ""
echo "🎯 Happy trading! 📊💰"