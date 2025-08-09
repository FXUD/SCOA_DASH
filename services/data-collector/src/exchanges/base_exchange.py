"""
交易所基类
定义所有交易所适配器的通用接口
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Balance:
    """账户余额数据结构"""
    asset: str
    free: float
    locked: float
    total: float
    timestamp: datetime
    

@dataclass
class Position:
    """持仓数据结构"""
    symbol: str
    side: str  # 'long' or 'short'
    size: float
    entry_price: float
    current_price: float
    pnl: float
    pnl_percentage: float
    timestamp: datetime


@dataclass
class Trade:
    """交易记录数据结构"""
    symbol: str
    side: str  # 'buy' or 'sell'
    amount: float
    price: float
    fee: float
    fee_asset: str
    timestamp: datetime
    trade_id: str


@dataclass
class MarketData:
    """市场数据结构"""
    symbol: str
    price: float
    volume_24h: float
    change_24h: float
    change_24h_percent: float
    high_24h: float
    low_24h: float
    timestamp: datetime


class BaseExchange(ABC):
    """交易所基类"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = config.get("name", "Unknown")
        self.api_key = config.get("api_key", "")
        self.api_secret = config.get("api_secret", "")
        self.sandbox = config.get("sandbox", False)
        self.enabled = config.get("enabled", False)
        self.symbols = config.get("symbols", [])
        self.rate_limit = config.get("rate_limit", 100)
        
        # 内部状态
        self._client = None
        self._last_request_time = {}
        self._request_count = 0
        
    @abstractmethod
    async def initialize(self) -> bool:
        """初始化交易所连接"""
        pass
    
    @abstractmethod
    async def close(self):
        """关闭连接"""
        pass
    
    @abstractmethod
    async def test_connection(self) -> bool:
        """测试API连接"""
        pass
    
    @abstractmethod
    async def get_account_balance(self) -> List[Balance]:
        """获取账户余额"""
        pass
    
    @abstractmethod
    async def get_positions(self) -> List[Position]:
        """获取持仓信息（现货交易返回空列表）"""
        pass
    
    @abstractmethod
    async def get_recent_trades(self, limit: int = 100) -> List[Trade]:
        """获取最近交易记录"""
        pass
    
    @abstractmethod
    async def get_market_data(self, symbols: Optional[List[str]] = None) -> List[MarketData]:
        """获取市场数据"""
        pass
    
    async def get_portfolio_value(self) -> Dict[str, float]:
        """计算投资组合总价值"""
        try:
            balances = await self.get_account_balance()
            market_data = await self.get_market_data()
            
            # 创建价格字典
            prices = {}
            for data in market_data:
                symbol = data.symbol.upper()
                if symbol.endswith('USDT'):
                    asset = symbol.replace('USDT', '')
                    prices[asset] = data.price
            
            # 计算总价值
            total_value = 0.0
            asset_values = {}
            
            for balance in balances:
                if balance.total > 0:
                    asset = balance.asset.upper()
                    if asset == 'USDT':
                        value = balance.total
                    elif asset in prices:
                        value = balance.total * prices[asset]
                    else:
                        value = 0.0
                    
                    asset_values[asset] = {
                        'amount': balance.total,
                        'value_usdt': value,
                        'price': prices.get(asset, 0.0)
                    }
                    total_value += value
            
            return {
                'total_value_usdt': total_value,
                'assets': asset_values,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            raise Exception(f"Failed to calculate portfolio value: {e}")
    
    def is_enabled(self) -> bool:
        """检查交易所是否启用"""
        return self.enabled and bool(self.api_key) and bool(self.api_secret)
    
    def get_symbols(self) -> List[str]:
        """获取要监控的交易对"""
        return self.symbols
    
    async def rate_limit_check(self):
        """速率限制检查"""
        import time
        import asyncio
        
        current_time = time.time()
        
        # 简单的速率限制实现
        if hasattr(self, '_last_request_time'):
            time_diff = current_time - self._last_request_time.get('last', 0)
            if time_diff < (60.0 / self.rate_limit):  # 转换为每秒请求数
                sleep_time = (60.0 / self.rate_limit) - time_diff
                await asyncio.sleep(sleep_time)
        
        self._last_request_time['last'] = time.time()