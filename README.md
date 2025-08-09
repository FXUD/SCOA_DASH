# SCOA 稳定币套利策略监控系统

实时监控 Binance 和 HTX 交易所的稳定币套利策略收益情况。

## 🚀 快速开始

### 1. 环境准备
```bash
# 安装 Docker 和 Docker Compose
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
```

### 2. 配置设置
```bash
# 复制配置文件
cp config/config.yml.example config/config.yml

# 编辑配置文件，添加你的 API 密钥
vim config/config.yml
```

### 3. 启动服务
```bash
# 启动所有服务
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f data-collector
```

## 📊 访问地址

- **Grafana Dashboard**: http://localhost:3033
- **默认登录**: admin / admin123

## 🔧 主要功能

- ✅ **双交易所监控**: Binance + HTX
- ✅ **实时汇率转换**: USDC/USDT, FDUSD/USDT 实时价格
- ✅ **USDT统一结算**: 所有资产按USDT等价值计算
- ✅ **收益率计算**: 24小时收益百分比
- ✅ **30秒更新**: 实时数据采集和展示

## 📋 Dashboard 展示

1. **独立资金曲线**: 每个交易所单独显示
2. **当前资金**: 实时余额（精确到小数点后两位）
3. **收益率**: 24小时收益百分比
4. **实时更新**: 30秒自动刷新

## 🛠️ 常用命令

```bash
# 停止服务
docker-compose down

# 重启服务
docker-compose restart

# 查看特定服务日志
docker-compose logs data-collector
docker-compose logs grafana
docker-compose logs influxdb

# 清理所有数据重新开始
docker-compose down -v
docker system prune -f
```

## ⚠️ 注意事项

1. 确保 `config/config.yml` 包含正确的 API 密钥
2. 不要将包含真实 API 密钥的配置文件提交到 Git
3. 首次启动可能需要几分钟来创建数据库和初始化 Grafana
4. 确保服务器防火墙开放 3033 端口（Grafana）

## 📈 系统架构

- **InfluxDB**: 时序数据存储
- **Grafana**: 数据可视化
- **Python Collector**: 数据采集服务
- **Redis**: 缓存服务

## 🔐 安全设置

- 修改默认的 Grafana 管理员密码
- 使用只读权限的 API 密钥
- 定期更换 API 密钥
- 配置防火墙限制访问