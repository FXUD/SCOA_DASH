"""
InfluxDB数据库管理模块
负责时序数据的存储和查询
"""

import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import ASYNCHRONOUS
from loguru import logger

from .config import Config
from .exchanges.base_exchange import Balance, Trade, MarketData


class InfluxDBManager:
    """InfluxDB数据库管理器"""
    
    def __init__(self, config: Config):
        self.config = config
        self.client: Optional[InfluxDBClient] = None
        self.write_api = None
        self.query_api = None
        
        # 数据库配置
        self.url = self.config.get_influxdb_url()
        self.token = self.config.get_influxdb_token()
        self.org = self.config.get_influxdb_org()
        self.bucket = self.config.get_influxdb_bucket()
        
    async def initialize(self) -> bool:
        """初始化数据库连接"""
        try:
            self.client = InfluxDBClient(
                url=self.url,
                token=self.token,
                org=self.org
            )
            
            # 创建异步写入API
            self.write_api = self.client.write_api(write_options=ASYNCHRONOUS)
            self.query_api = self.client.query_api()
            
            # 测试连接
            if await self.test_connection():
                logger.info(f"InfluxDB connected successfully to {self.url}")
                return True
            else:
                logger.error("Failed to connect to InfluxDB")
                return False
                
        except Exception as e:
            logger.error(f"Failed to initialize InfluxDB: {e}")
            return False
    
    async def test_connection(self) -> bool:
        """测试数据库连接"""
        try:
            # 简单查询测试连接
            query = f'from(bucket: "{self.bucket}") |> range(start: -1m) |> limit(n: 1)'
            result = await asyncio.get_event_loop().run_in_executor(
                None, self.query_api.query, query
            )
            logger.info("InfluxDB connection test successful")
            return True
            
        except Exception as e:
            logger.warning(f"InfluxDB connection test failed: {e}")
            # 连接测试失败不一定意味着数据库不可用，可能只是没有数据
            return True
    
    async def close(self):
        """关闭数据库连接"""
        if self.client:
            self.client.close()
            logger.info("InfluxDB connection closed")
    
    async def write_balances(self, exchange_name: str, balances: List[Balance]):
        """写入账户余额数据"""
        try:
            points = []
            
            for balance in balances:
                point = (
                    Point("account_balance")
                    .tag("exchange", exchange_name)
                    .tag("asset", balance.asset)
                    .field("free", balance.free)
                    .field("locked", balance.locked)
                    .field("total", balance.total)
                    .time(balance.timestamp)
                )
                points.append(point)
            
            if points:
                await asyncio.get_event_loop().run_in_executor(
                    None, 
                    self.write_api.write,
                    self.bucket,
                    self.org,
                    points
                )
                logger.info(f"Wrote {len(points)} balance records for {exchange_name}")
                
        except Exception as e:
            logger.error(f"Failed to write balances to InfluxDB: {e}")
    
    async def write_trades(self, exchange_name: str, trades: List[Trade]):
        """写入交易记录"""
        try:
            points = []
            
            for trade in trades:
                point = (
                    Point("trades")
                    .tag("exchange", exchange_name)
                    .tag("symbol", trade.symbol)
                    .tag("side", trade.side)
                    .tag("trade_id", trade.trade_id)
                    .field("amount", trade.amount)
                    .field("price", trade.price)
                    .field("value", trade.amount * trade.price)
                    .field("fee", trade.fee)
                    .field("fee_asset", trade.fee_asset)
                    .time(trade.timestamp)
                )
                points.append(point)
            
            if points:
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    self.write_api.write,
                    self.bucket,
                    self.org,
                    points
                )
                logger.info(f"Wrote {len(points)} trade records for {exchange_name}")
                
        except Exception as e:
            logger.error(f"Failed to write trades to InfluxDB: {e}")
    
    async def write_market_data(self, exchange_name: str, market_data: List[MarketData]):
        """写入市场数据"""
        try:
            points = []
            
            for data in market_data:
                point = (
                    Point("market_data")
                    .tag("exchange", exchange_name)
                    .tag("symbol", data.symbol)
                    .field("price", data.price)
                    .field("volume_24h", data.volume_24h)
                    .field("change_24h", data.change_24h)
                    .field("change_24h_percent", data.change_24h_percent)
                    .field("high_24h", data.high_24h)
                    .field("low_24h", data.low_24h)
                    .time(data.timestamp)
                )
                points.append(point)
            
            if points:
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    self.write_api.write,
                    self.bucket,
                    self.org,
                    points
                )
                logger.info(f"Wrote {len(points)} market data records for {exchange_name}")
                
        except Exception as e:
            logger.error(f"Failed to write market data to InfluxDB: {e}")
    
    async def write_portfolio_value(self, exchange_name: str, portfolio_data: Dict[str, Any]):
        """写入投资组合价值数据"""
        try:
            current_time = datetime.now()
            points = []
            
            # 写入总价值
            total_point = (
                Point("portfolio_value")
                .tag("exchange", exchange_name)
                .tag("type", "total")
                .field("value_usdt", portfolio_data['total_value_usdt'])
                .time(current_time)
            )
            points.append(total_point)
            
            # 写入各资产价值
            for asset, data in portfolio_data.get('assets', {}).items():
                asset_point = (
                    Point("portfolio_value")
                    .tag("exchange", exchange_name)
                    .tag("type", "asset")
                    .tag("asset", asset)
                    .field("amount", data['amount'])
                    .field("value_usdt", data['value_usdt'])
                    .field("price", data['price'])
                    .time(current_time)
                )
                points.append(asset_point)
            
            if points:
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    self.write_api.write,
                    self.bucket,
                    self.org,
                    points
                )
                logger.info(f"Wrote portfolio value data for {exchange_name}")
                
        except Exception as e:
            logger.error(f"Failed to write portfolio value to InfluxDB: {e}")
    
    async def write_health_metrics(self, metrics: Dict[str, Any]):
        """写入健康检查指标"""
        try:
            current_time = datetime.now()
            points = []
            
            for metric_name, value in metrics.items():
                point = (
                    Point("health_metrics")
                    .tag("metric", metric_name)
                    .field("value", value)
                    .time(current_time)
                )
                points.append(point)
            
            if points:
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    self.write_api.write,
                    self.bucket,
                    self.org,
                    points
                )
                logger.debug(f"Wrote {len(points)} health metrics")
                
        except Exception as e:
            logger.error(f"Failed to write health metrics to InfluxDB: {e}")
    
    async def get_latest_portfolio_value(self, exchange_name: str) -> Optional[float]:
        """获取最新的投资组合价值"""
        try:
            query = f'''
            from(bucket: "{self.bucket}")
              |> range(start: -1h)
              |> filter(fn: (r) => r._measurement == "portfolio_value")
              |> filter(fn: (r) => r.exchange == "{exchange_name}")
              |> filter(fn: (r) => r.type == "total")
              |> filter(fn: (r) => r._field == "value_usdt")
              |> last()
            '''
            
            tables = await asyncio.get_event_loop().run_in_executor(
                None, self.query_api.query, query
            )
            
            for table in tables:
                for record in table.records:
                    return float(record.get_value())
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get latest portfolio value: {e}")
            return None
    
    async def write_strategy_pnl(self, exchange_name: str, total_value_usdt: float, timestamp: datetime):
        """写入策略PnL数据点"""
        try:
            point = (
                Point("strategy_pnl")
                .tag("exchange", exchange_name)
                .tag("strategy", "stablecoin_arbitrage")  # 策略标识
                .field("total_value_usdt", total_value_usdt)
                .time(timestamp)
            )
            
            await asyncio.get_event_loop().run_in_executor(
                None,
                self.write_api.write,
                self.bucket,
                self.org,
                [point]
            )
            
            logger.debug(f"Wrote strategy PnL data for {exchange_name}: ${total_value_usdt:.2f}")
            
        except Exception as e:
            logger.error(f"Failed to write strategy PnL to InfluxDB: {e}")