#!/bin/bash

# SCOA Dashboard 日志查看脚本
# 用于查看服务日志

# 获取脚本所在目录的父目录作为项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo "📋 SCOA Dashboard - Service Logs"
echo "================================"

# 检查参数
if [ $# -eq 0 ]; then
    echo "📊 Showing all service logs (press Ctrl+C to exit)..."
    echo ""
    docker-compose logs -f
elif [ "$1" = "data-collector" ]; then
    echo "🤖 Showing data collector logs..."
    docker-compose logs -f data-collector
elif [ "$1" = "grafana" ]; then
    echo "📈 Showing Grafana logs..."
    docker-compose logs -f grafana
elif [ "$1" = "influxdb" ]; then
    echo "📊 Showing InfluxDB logs..."
    docker-compose logs -f influxdb
elif [ "$1" = "redis" ]; then
    echo "🔄 Showing Redis logs..."
    docker-compose logs -f redis
elif [ "$1" = "list" ]; then
    echo "📋 Available services:"
    echo "   - data-collector (Python data collection service)"
    echo "   - grafana (Dashboard and visualization)"
    echo "   - influxdb (Time series database)"
    echo "   - redis (Caching service)"
    echo ""
    echo "Usage examples:"
    echo "   ./scripts/logs.sh                 # All services"
    echo "   ./scripts/logs.sh data-collector  # Data collector only"
    echo "   ./scripts/logs.sh grafana         # Grafana only"
    exit 0
else
    echo "❌ Unknown service: $1"
    echo ""
    echo "📋 Available services: data-collector, grafana, influxdb, redis"
    echo "💡 Use './scripts/logs.sh list' to see all options"
    exit 1
fi