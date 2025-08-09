"""
稳定币套利计算器
计算FDUSD/USDT vs USDC/USDT的价差和套利机会
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
from loguru import logger


@dataclass
class ArbitrageOpportunity:
    """套利机会数据结构"""
    timestamp: datetime
    binance_price: float
    htx_price: float
    price_diff: float
    price_diff_percent: float
    suggested_action: str  # 'buy_binance_sell_htx', 'buy_htx_sell_binance', 'no_action'
    potential_profit_percent: float
    

@dataclass
class PnLData:
    """PnL数据结构"""
    timestamp: datetime
    total_value_usdt: float
    binance_balance_usdt: float
    htx_balance_usdt: float
    daily_pnl: float
    daily_pnl_percent: float
    cumulative_pnl: float
    cumulative_pnl_percent: float


class ArbitrageCalculator:
    """稳定币套利计算器"""
    
    def __init__(self, initial_capital: float = 10000.0):
        self.initial_capital = initial_capital
        self.transaction_fee = 0.001  # 0.1% 手续费
        self.min_profit_threshold = 0.05  # 最小5个基点才考虑套利
        self.price_history = []
        self.pnl_history = []
        
    def calculate_arbitrage_opportunity(
        self, 
        binance_price: float, 
        htx_price: float,
        timestamp: Optional[datetime] = None
    ) -> ArbitrageOpportunity:
        """计算套利机会"""
        if timestamp is None:
            timestamp = datetime.now()
            
        # 计算价差
        price_diff = binance_price - htx_price
        price_diff_percent = (price_diff / ((binance_price + htx_price) / 2)) * 100
        
        # 计算潜在利润（考虑手续费）
        potential_profit = abs(price_diff_percent) - (self.transaction_fee * 2 * 100)
        
        # 判断套利方向
        if price_diff_percent > self.min_profit_threshold:
            suggested_action = "buy_htx_sell_binance"  # HTX便宜，Binance贵
        elif price_diff_percent < -self.min_profit_threshold:
            suggested_action = "buy_binance_sell_htx"  # Binance便宜，HTX贵
        else:
            suggested_action = "no_action"
        
        opportunity = ArbitrageOpportunity(
            timestamp=timestamp,
            binance_price=binance_price,
            htx_price=htx_price,
            price_diff=price_diff,
            price_diff_percent=price_diff_percent,
            suggested_action=suggested_action,
            potential_profit_percent=max(0, potential_profit)
        )
        
        self.price_history.append(opportunity)
        return opportunity
    
    def calculate_pnl(
        self, 
        binance_balance: Dict[str, float],
        htx_balance: Dict[str, float],
        current_prices: Dict[str, float],
        timestamp: Optional[datetime] = None
    ) -> PnLData:
        """计算PnL数据"""
        if timestamp is None:
            timestamp = datetime.now()
            
        # 计算各交易所USDT总价值
        binance_total = self._calculate_total_value_usdt(binance_balance, current_prices)
        htx_total = self._calculate_total_value_usdt(htx_balance, current_prices)
        total_value = binance_total + htx_total
        
        # 计算PnL
        daily_pnl = 0.0
        daily_pnl_percent = 0.0
        cumulative_pnl = total_value - self.initial_capital
        cumulative_pnl_percent = (cumulative_pnl / self.initial_capital) * 100
        
        # 如果有历史数据，计算日PnL
        if self.pnl_history:
            last_pnl = self.pnl_history[-1]
            # 检查是否是新的一天
            if timestamp.date() != last_pnl.timestamp.date():
                daily_pnl = total_value - last_pnl.total_value_usdt
                daily_pnl_percent = (daily_pnl / last_pnl.total_value_usdt) * 100
        
        pnl_data = PnLData(
            timestamp=timestamp,
            total_value_usdt=total_value,
            binance_balance_usdt=binance_total,
            htx_balance_usdt=htx_total,
            daily_pnl=daily_pnl,
            daily_pnl_percent=daily_pnl_percent,
            cumulative_pnl=cumulative_pnl,
            cumulative_pnl_percent=cumulative_pnl_percent
        )
        
        self.pnl_history.append(pnl_data)
        return pnl_data
    
    def _calculate_total_value_usdt(
        self, 
        balance: Dict[str, float], 
        prices: Dict[str, float]
    ) -> float:
        """计算账户总USDT价值"""
        total_value = 0.0
        
        for asset, amount in balance.items():
            if amount <= 0:
                continue
                
            if asset.upper() == 'USDT':
                total_value += amount
            elif asset.upper() == 'FDUSD':
                # FDUSD按其对USDT的价格计算
                fdusd_price = prices.get('fdusd_usdt', 1.0)  # 默认1:1
                total_value += amount * fdusd_price
            elif asset.upper() == 'USDC':
                # USDC按其对USDT的价格计算
                usdc_price = prices.get('usdc_usdt', 1.0)  # 默认1:1
                total_value += amount * usdc_price
            else:
                # 其他资产忽略或按特定价格计算
                logger.debug(f"Unknown asset for valuation: {asset}")
                
        return total_value
    
    def get_recent_opportunities(self, hours: int = 24) -> List[ArbitrageOpportunity]:
        """获取最近的套利机会"""
        cutoff_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff_time = cutoff_time.replace(hour=cutoff_time.hour - hours)
        
        return [
            opp for opp in self.price_history 
            if opp.timestamp >= cutoff_time
        ]
    
    def get_recent_pnl(self, days: int = 30) -> List[PnLData]:
        """获取最近的PnL数据"""
        cutoff_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff_time = cutoff_time.replace(day=cutoff_time.day - days)
        
        return [
            pnl for pnl in self.pnl_history 
            if pnl.timestamp >= cutoff_time
        ]
    
    def get_performance_stats(self) -> Dict[str, float]:
        """获取策略表现统计"""
        if not self.pnl_history:
            return {}
            
        latest_pnl = self.pnl_history[-1]
        
        # 计算最大回撤
        max_value = self.initial_capital
        max_drawdown = 0.0
        
        for pnl in self.pnl_history:
            max_value = max(max_value, pnl.total_value_usdt)
            drawdown = (max_value - pnl.total_value_usdt) / max_value * 100
            max_drawdown = max(max_drawdown, drawdown)
        
        # 计算年化收益率（假设）
        days_running = max(1, (datetime.now() - self.pnl_history[0].timestamp).days)
        annualized_return = (latest_pnl.cumulative_pnl_percent / days_running) * 365
        
        # 计算夏普比率（简化版）
        daily_returns = []
        for i in range(1, len(self.pnl_history)):
            prev_value = self.pnl_history[i-1].total_value_usdt
            curr_value = self.pnl_history[i].total_value_usdt
            daily_return = (curr_value - prev_value) / prev_value
            daily_returns.append(daily_return)
        
        if daily_returns:
            import statistics
            avg_return = statistics.mean(daily_returns) * 365
            return_std = statistics.stdev(daily_returns) * (365 ** 0.5) if len(daily_returns) > 1 else 0
            sharpe_ratio = avg_return / return_std if return_std > 0 else 0
        else:
            sharpe_ratio = 0
            
        return {
            'total_return_percent': latest_pnl.cumulative_pnl_percent,
            'annualized_return_percent': annualized_return,
            'max_drawdown_percent': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'days_running': days_running,
            'current_value_usdt': latest_pnl.total_value_usdt
        }