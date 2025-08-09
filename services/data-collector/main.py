#!/usr/bin/env python3
"""
SCOA Dashboard Data Collector
主要数据收集服务，用于从加密货币交易所收集交易数据
"""

import asyncio
import sys
import signal
from pathlib import Path

from loguru import logger
from src.config import Config
from src.data_collector import DataCollector
from src.database import InfluxDBManager


class ScoaDashboard:
    def __init__(self):
        self.config = Config()
        self.db_manager = None
        self.data_collector = None
        self.running = False
        
    async def initialize(self):
        """初始化所有组件"""
        try:
            # 配置日志
            self._setup_logging()
            
            # 初始化数据库连接
            self.db_manager = InfluxDBManager(self.config)
            await self.db_manager.initialize()
            
            # 初始化数据收集器
            self.data_collector = DataCollector(self.config, self.db_manager)
            await self.data_collector.initialize()
            
            logger.info("SCOA Dashboard initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize: {e}")
            return False
    
    def _setup_logging(self):
        """配置日志系统"""
        log_level = self.config.get_log_level()
        log_file = self.config.get_log_file()
        
        # 移除默认handler
        logger.remove()
        
        # 添加控制台输出
        logger.add(
            sys.stderr,
            level=log_level,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
        )
        
        # 添加文件输出
        if log_file:
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            logger.add(
                log_file,
                level=log_level,
                format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
                rotation="1 day",
                retention="30 days",
                compression="gz"
            )
    
    async def start(self):
        """启动数据收集服务"""
        self.running = True
        logger.info("Starting SCOA Dashboard data collection service")
        
        try:
            await self.data_collector.start()
        except Exception as e:
            logger.error(f"Error in data collection service: {e}")
            self.running = False
    
    async def stop(self):
        """停止服务"""
        logger.info("Stopping SCOA Dashboard service")
        self.running = False
        
        if self.data_collector:
            await self.data_collector.stop()
        
        if self.db_manager:
            await self.db_manager.close()
    
    def handle_signal(self, sig, frame):
        """处理系统信号"""
        logger.info(f"Received signal {sig}, shutting down...")
        self.running = False


async def main():
    """主函数"""
    dashboard = ScoaDashboard()
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, dashboard.handle_signal)
    signal.signal(signal.SIGTERM, dashboard.handle_signal)
    
    # 初始化
    if not await dashboard.initialize():
        sys.exit(1)
    
    # 启动服务
    try:
        await dashboard.start()
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt")
    finally:
        await dashboard.stop()
    
    logger.info("SCOA Dashboard service stopped")


if __name__ == "__main__":
    asyncio.run(main())