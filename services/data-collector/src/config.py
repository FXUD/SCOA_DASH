"""
配置管理模块
负责加载和管理YAML配置文件
"""

import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from loguru import logger


class Config:
    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            # 默认配置文件路径（Docker容器内）
            config_path = Path("/app/config/config.yml")
        
        self.config_path = Path(config_path)
        self.config_data = {}
        self.load_config()
    
    def load_config(self):
        """加载配置文件"""
        try:
            if not self.config_path.exists():
                raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config_data = yaml.safe_load(f)
            
            logger.info(f"Configuration loaded from: {self.config_path}")
            
        except Exception as e:
            logger.error(f"Failed to load configuration: {e}")
            raise
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        通过点分路径获取配置值
        例: get("app.name") -> config_data["app"]["name"]
        """
        keys = key_path.split('.')
        value = self.config_data
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
    
    # App配置
    def get_app_name(self) -> str:
        return self.get("app.name", "SCOA Dashboard")
    
    def get_app_version(self) -> str:
        return self.get("app.version", "1.0.0")
    
    def is_debug_mode(self) -> bool:
        return self.get("app.debug", False)
    
    def get_log_level(self) -> str:
        return self.get("app.log_level", "INFO")
    
    def get_log_file(self) -> Optional[str]:
        return self.get("app.log_file")
    
    # InfluxDB配置
    def get_influxdb_config(self) -> Dict[str, Any]:
        return self.get("influxdb", {})
    
    def get_influxdb_url(self) -> str:
        config = self.get_influxdb_config()
        host = config.get("host", "localhost")
        port = config.get("port", 8086)
        return f"http://{host}:{port}"
    
    def get_influxdb_token(self) -> str:
        return self.get("influxdb.token", "")
    
    def get_influxdb_org(self) -> str:
        return self.get("influxdb.organization", "scoa")
    
    def get_influxdb_bucket(self) -> str:
        return self.get("influxdb.bucket", "trading_data")
    
    # 数据收集配置
    def get_collection_interval(self) -> int:
        return self.get("data_collection.interval_minutes", 5)
    
    def get_batch_size(self) -> int:
        return self.get("data_collection.batch_size", 100)
    
    def get_retry_attempts(self) -> int:
        return self.get("data_collection.retry_attempts", 3)
    
    def get_request_timeout(self) -> int:
        return self.get("data_collection.timeout_seconds", 30)
    
    def get_concurrent_requests(self) -> int:
        return self.get("data_collection.concurrent_requests", 5)
    
    # 交易所配置
    def get_exchanges_config(self) -> Dict[str, Any]:
        return self.get("exchanges", {})
    
    def get_exchange_config(self, exchange_name: str) -> Optional[Dict[str, Any]]:
        return self.get(f"exchanges.{exchange_name}")
    
    def is_exchange_enabled(self, exchange_name: str) -> bool:
        exchange_config = self.get_exchange_config(exchange_name)
        if exchange_config:
            return exchange_config.get("enabled", False)
        return False
    
    def get_enabled_exchanges(self) -> list:
        """获取所有启用的交易所列表"""
        exchanges = []
        for exchange_name, config in self.get_exchanges_config().items():
            if config.get("enabled", False):
                exchanges.append(exchange_name)
        return exchanges
    
    # 性能配置
    def get_max_workers(self) -> int:
        return self.get("performance.max_workers", 4)
    
    def get_connection_pool_size(self) -> int:
        return self.get("performance.connection_pool_size", 20)
    
    # 监控配置
    def get_health_check_interval(self) -> int:
        return self.get("monitoring.health_check_interval", 60)
    
    def get_metrics_retention_days(self) -> int:
        return self.get("monitoring.metrics_retention_days", 30)