"""
数据收集器主模块
协调所有交易所的数据收集任务
"""

import asyncio
import time
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from loguru import logger

from .config import Config
from .database import InfluxDBManager
from .exchanges.binance_exchange import BinanceExchange
from .exchanges.htx_exchange import HTXExchange
from .exchanges.base_exchange import BaseExchange
from .arbitrage_calculator import ArbitrageCalculator


class DataCollector:
    """数据收集器"""
    
    def __init__(self, config: Config, db_manager: InfluxDBManager):
        self.config = config
        self.db_manager = db_manager
        self.exchanges: Dict[str, BaseExchange] = {}
        self.running = False
        
        # 收集任务配置
        self.collection_interval = self.config.get_collection_interval() * 60  # 转换为秒
        self.concurrent_requests = self.config.get_concurrent_requests()
        
        # 初始化套利计算器
        self.arbitrage_calculator = ArbitrageCalculator()
        
        # 统计信息
        self.stats = {
            'collections_completed': 0,
            'collections_failed': 0,
            'last_collection_time': None,
            'total_runtime': 0,
            'start_time': None
        }
    
    async def initialize(self):
        """初始化所有交易所连接"""
        try:
            enabled_exchanges = self.config.get_enabled_exchanges()
            logger.info(f"Initializing exchanges: {enabled_exchanges}")
            
            for exchange_name in enabled_exchanges:
                exchange_config = self.config.get_exchange_config(exchange_name)
                if not exchange_config:
                    logger.warning(f"No configuration found for exchange: {exchange_name}")
                    continue
                
                # 创建交易所实例
                exchange = await self._create_exchange(exchange_name, exchange_config)
                if exchange and await exchange.initialize():
                    self.exchanges[exchange_name] = exchange
                    logger.info(f"Successfully initialized {exchange_name}")
                else:
                    logger.error(f"Failed to initialize {exchange_name}")
            
            if not self.exchanges:
                raise Exception("No exchanges were successfully initialized")
                
            logger.info(f"Data collector initialized with {len(self.exchanges)} exchanges")
            
        except Exception as e:
            logger.error(f"Failed to initialize data collector: {e}")
            raise
    
    async def _create_exchange(self, exchange_name: str, config: Dict) -> Optional[BaseExchange]:
        """创建交易所实例"""
        try:
            if exchange_name.lower() == 'binance':
                return BinanceExchange(config)
            elif exchange_name.lower() == 'htx':
                return HTXExchange(config)
            else:
                logger.warning(f"Unknown exchange type: {exchange_name}")
                return None
                
        except Exception as e:
            logger.error(f"Failed to create exchange {exchange_name}: {e}")
            return None
    
    async def start(self):
        """启动数据收集服务"""
        self.running = True
        self.stats['start_time'] = datetime.now()
        
        logger.info(f"Starting data collection with {self.collection_interval}s interval")
        
        # 启动健康检查任务
        health_task = asyncio.create_task(self._health_check_loop())
        
        try:
            while self.running:
                collection_start = time.time()
                
                # 执行数据收集
                await self._collect_data_round()
                
                # 更新统计信息
                collection_time = time.time() - collection_start
                self.stats['last_collection_time'] = datetime.now()
                self.stats['total_runtime'] = time.time() - self.stats['start_time'].timestamp()
                
                logger.info(f"Data collection completed in {collection_time:.2f}s")
                
                # 等待下一个收集周期
                if self.running:
                    await asyncio.sleep(self.collection_interval)
                    
        except Exception as e:
            logger.error(f"Error in data collection loop: {e}")
        finally:
            health_task.cancel()
            await self.stop()
    
    async def _collect_data_round(self):
        """执行一轮数据收集"""
        try:
            # 并发收集所有交易所数据
            tasks = []
            for exchange_name, exchange in self.exchanges.items():
                task = asyncio.create_task(
                    self._collect_exchange_data(exchange_name, exchange),
                    name=f"collect_{exchange_name}"
                )
                tasks.append(task)
            
            # 等待所有任务完成
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 统计结果
            successful = sum(1 for result in results if result is True)
            failed = len(results) - successful
            
            self.stats['collections_completed'] += successful
            self.stats['collections_failed'] += failed
            
            if failed > 0:
                logger.warning(f"Collection round completed: {successful} successful, {failed} failed")
            else:
                logger.info(f"Collection round completed: {successful} exchanges processed successfully")
            
            # 收集套利策略PnL数据
            await self._collect_strategy_pnl()
                
        except Exception as e:
            logger.error(f"Error in data collection round: {e}")
            self.stats['collections_failed'] += 1
    
    async def _collect_exchange_data(self, exchange_name: str, exchange: BaseExchange) -> bool:
        """收集单个交易所的数据"""
        try:
            if not exchange.is_enabled():
                logger.warning(f"Exchange {exchange_name} is not enabled")
                return False
            
            logger.debug(f"Collecting data from {exchange_name}")
            
            # 并发收集不同类型的数据
            tasks = [
                self._collect_balance_data(exchange_name, exchange),
                self._collect_market_data(exchange_name, exchange),
                self._collect_trade_data(exchange_name, exchange),
                self._collect_portfolio_data(exchange_name, exchange),
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 检查结果
            successful = sum(1 for result in results if result is True)
            total = len(results)
            
            if successful == total:
                logger.debug(f"Successfully collected all data types from {exchange_name}")
                return True
            else:
                logger.warning(f"Partial success for {exchange_name}: {successful}/{total} data types collected")
                return successful > 0
            
        except Exception as e:
            logger.error(f"Failed to collect data from {exchange_name}: {e}")
            return False
    
    async def _collect_balance_data(self, exchange_name: str, exchange: BaseExchange) -> bool:
        """收集余额数据"""
        try:
            balances = await exchange.get_account_balance()
            if balances:
                await self.db_manager.write_balances(exchange_name, balances)
                logger.debug(f"Collected {len(balances)} balance records from {exchange_name}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Failed to collect balance data from {exchange_name}: {e}")
            return False
    
    async def _collect_market_data(self, exchange_name: str, exchange: BaseExchange) -> bool:
        """收集市场数据"""
        try:
            market_data = await exchange.get_market_data()
            if market_data:
                await self.db_manager.write_market_data(exchange_name, market_data)
                logger.debug(f"Collected market data for {len(market_data)} symbols from {exchange_name}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Failed to collect market data from {exchange_name}: {e}")
            return False
    
    async def _collect_trade_data(self, exchange_name: str, exchange: BaseExchange) -> bool:
        """收集交易数据"""
        try:
            trades = await exchange.get_recent_trades(limit=50)
            if trades:
                await self.db_manager.write_trades(exchange_name, trades)
                logger.debug(f"Collected {len(trades)} trade records from {exchange_name}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Failed to collect trade data from {exchange_name}: {e}")
            return False
    
    async def _collect_portfolio_data(self, exchange_name: str, exchange: BaseExchange) -> bool:
        """收集投资组合数据"""
        try:
            portfolio_value = await exchange.get_portfolio_value()
            if portfolio_value and portfolio_value['total_value_usdt'] > 0:
                await self.db_manager.write_portfolio_value(exchange_name, portfolio_value)
                logger.debug(f"Collected portfolio value from {exchange_name}: ${portfolio_value['total_value_usdt']:.2f}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Failed to collect portfolio data from {exchange_name}: {e}")
            return False
    
    async def _collect_strategy_pnl(self):
        """收集策略PnL数据 - 简化版本，只收集各交易所总资金"""
        try:
            current_time = datetime.now()
            
            # 收集每个交易所的总资金价值
            for exchange_name, exchange in self.exchanges.items():
                try:
                    portfolio_value = await exchange.get_portfolio_value()
                    
                    if portfolio_value and portfolio_value['total_value_usdt'] > 0:
                        # 写入策略PnL数据点
                        await self.db_manager.write_strategy_pnl(
                            exchange_name, 
                            portfolio_value['total_value_usdt'],
                            current_time
                        )
                        
                        logger.debug(f"Strategy PnL recorded for {exchange_name}: ${portfolio_value['total_value_usdt']:.2f}")
                        
                except Exception as e:
                    logger.error(f"Failed to collect strategy PnL for {exchange_name}: {e}")
                    continue
                    
            logger.info("Strategy PnL data collection completed")
            
        except Exception as e:
            logger.error(f"Error collecting strategy PnL: {e}")
    
    async def _health_check_loop(self):
        """健康检查循环"""
        health_interval = self.config.get_health_check_interval()
        
        while self.running:
            try:
                await asyncio.sleep(health_interval)
                
                if self.running:
                    # 收集健康指标
                    health_metrics = {
                        'collections_completed': self.stats['collections_completed'],
                        'collections_failed': self.stats['collections_failed'],
                        'exchanges_active': len(self.exchanges),
                        'total_runtime_seconds': self.stats['total_runtime'],
                        'memory_usage_mb': await self._get_memory_usage(),
                    }
                    
                    # 写入健康指标
                    await self.db_manager.write_health_metrics(health_metrics)
                    
                    logger.debug(f"Health check: {health_metrics}")
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health check: {e}")
    
    async def _get_memory_usage(self) -> float:
        """获取内存使用量（MB）"""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss / 1024 / 1024
        except ImportError:
            return 0.0
    
    async def stop(self):
        """停止数据收集服务"""
        logger.info("Stopping data collection service")
        self.running = False
        
        # 关闭所有交易所连接
        for exchange_name, exchange in self.exchanges.items():
            try:
                await exchange.close()
                logger.info(f"Closed connection to {exchange_name}")
            except Exception as e:
                logger.error(f"Error closing {exchange_name}: {e}")
        
        # 显示统计信息
        runtime = self.stats['total_runtime']
        completed = self.stats['collections_completed']
        failed = self.stats['collections_failed']
        
        logger.info(f"Data collection stopped. Runtime: {runtime:.0f}s, Completed: {completed}, Failed: {failed}")
    
    def get_status(self) -> Dict:
        """获取收集器状态"""
        return {
            'running': self.running,
            'exchanges': list(self.exchanges.keys()),
            'stats': self.stats.copy(),
            'config': {
                'collection_interval': self.collection_interval,
                'concurrent_requests': self.concurrent_requests,
            }
        }