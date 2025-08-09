"""
Binance交易所适配器
实现Binance现货交易API集成
"""

import ccxt
from typing import Dict, List, Any, Optional
from datetime import datetime
from loguru import logger

from .base_exchange import BaseExchange, Balance, Position, Trade, MarketData


class BinanceExchange(BaseExchange):
    """Binance交易所适配器"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.exchange_id = 'binance'
        
    async def initialize(self) -> bool:
        """初始化Binance连接"""
        try:
            # 创建CCXT客户端
            self._client = ccxt.binance({
                'apiKey': self.api_key,
                'secret': self.api_secret,
                'sandbox': self.sandbox,
                'rateLimit': 60000 / self.rate_limit,  # 转换为毫秒
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'spot',  # 现货交易
                }
            })
            
            # 测试连接
            if await self.test_connection():
                logger.info(f"Binance exchange initialized successfully")
                return True
            else:
                logger.error("Failed to connect to Binance")
                return False
                
        except Exception as e:
            logger.error(f"Failed to initialize Binance exchange: {e}")
            return False
    
    async def close(self):
        """关闭连接"""
        if self._client:
            self._client.close()
            logger.info("Binance connection closed")
    
    async def test_connection(self) -> bool:
        """测试API连接"""
        try:
            # 使用简单的市场数据API测试连接
            response = self._client.fetch_ticker('BTCUSDT')
            return 'symbol' in response and response['symbol'] == 'BTC/USDT'
            
        except Exception as e:
            logger.error(f"Binance connection test failed: {e}")
            return False
    
    async def get_account_balance(self) -> List[Balance]:
        """获取账户余额"""
        try:
            await self.rate_limit_check()
            balance_data = self._client.fetch_balance()
            
            balances = []
            current_time = datetime.now()
            
            for asset, data in balance_data.get('total', {}).items():
                if isinstance(data, (int, float)) and data > 0:
                    free = balance_data.get('free', {}).get(asset, 0.0)
                    used = balance_data.get('used', {}).get(asset, 0.0)
                    
                    balance = Balance(
                        asset=asset,
                        free=float(free),
                        locked=float(used),
                        total=float(data),
                        timestamp=current_time
                    )
                    balances.append(balance)
            
            logger.info(f"Retrieved {len(balances)} non-zero balances from Binance")
            return balances
            
        except Exception as e:
            logger.error(f"Failed to get Binance account balance: {e}")
            return []
    
    async def get_positions(self) -> List[Position]:
        """获取持仓信息（现货交易返回空列表）"""
        return []
    
    async def get_recent_trades(self, limit: int = 100) -> List[Trade]:
        """获取最近交易记录"""
        try:
            await self.rate_limit_check()
            
            all_trades = []
            
            # 对每个监控的交易对获取交易记录
            for symbol in self.symbols:
                try:
                    trades_data = self._client.fetch_my_trades(symbol, limit=limit)
                    
                    for trade_data in trades_data:
                        trade = Trade(
                            symbol=trade_data['symbol'],
                            side=trade_data['side'],
                            amount=float(trade_data['amount']),
                            price=float(trade_data['price']),
                            fee=float(trade_data.get('fee', {}).get('cost', 0.0)),
                            fee_asset=trade_data.get('fee', {}).get('currency', ''),
                            timestamp=datetime.fromtimestamp(trade_data['timestamp'] / 1000),
                            trade_id=str(trade_data['id'])
                        )
                        all_trades.append(trade)
                        
                except Exception as e:
                    logger.warning(f"Failed to get trades for {symbol}: {e}")
                    continue
            
            # 按时间排序
            all_trades.sort(key=lambda x: x.timestamp, reverse=True)
            
            logger.info(f"Retrieved {len(all_trades)} recent trades from Binance")
            return all_trades[:limit]
            
        except Exception as e:
            logger.error(f"Failed to get Binance recent trades: {e}")
            return []
    
    async def get_market_data(self, symbols: Optional[List[str]] = None) -> List[MarketData]:
        """获取市场数据"""
        try:
            await self.rate_limit_check()
            
            target_symbols = symbols or self.symbols
            market_data_list = []
            current_time = datetime.now()
            
            # 获取24小时统计数据
            tickers = self._client.fetch_tickers(target_symbols)
            
            for symbol, ticker in tickers.items():
                if symbol in target_symbols:
                    market_data = MarketData(
                        symbol=symbol,
                        price=float(ticker['last']),
                        volume_24h=float(ticker['baseVolume']),
                        change_24h=float(ticker['change']) if ticker['change'] else 0.0,
                        change_24h_percent=float(ticker['percentage']) if ticker['percentage'] else 0.0,
                        high_24h=float(ticker['high']),
                        low_24h=float(ticker['low']),
                        timestamp=current_time
                    )
                    market_data_list.append(market_data)
            
            logger.info(f"Retrieved market data for {len(market_data_list)} symbols from Binance")
            return market_data_list
            
        except Exception as e:
            logger.error(f"Failed to get Binance market data: {e}")
            return []
    
    async def get_trading_fees(self) -> Dict[str, Any]:
        """获取交易手续费"""
        try:
            await self.rate_limit_check()
            fees = self._client.fetch_trading_fees()
            return fees
            
        except Exception as e:
            logger.error(f"Failed to get Binance trading fees: {e}")
            return {}
    
    async def get_order_book(self, symbol: str, limit: int = 100) -> Dict[str, Any]:
        """获取订单簿"""
        try:
            await self.rate_limit_check()
            order_book = self._client.fetch_order_book(symbol, limit)
            return order_book
            
        except Exception as e:
            logger.error(f"Failed to get Binance order book for {symbol}: {e}")
            return {}