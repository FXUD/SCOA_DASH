#!/usr/bin/env python3
"""
简化的SCOA稳定币套利数据收集器
直接获取账户余额，计算USDT总价值，每30秒写入InfluxDB
"""

import asyncio
import time
import ccxt
import requests
import hmac
import hashlib
import base64
import urllib.parse
from datetime import datetime
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
from loguru import logger
import yaml
import sys


class HTXApi:
    """HTX现货API直接调用类"""
    def __init__(self, api_key, api_secret):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://api.huobi.pro"
    
    def _create_signature(self, method, endpoint, params):
        """创建API签名"""
        timestamp = datetime.utcnow().isoformat()[0:19]
        
        # 标准认证参数
        auth_params = {
            'AccessKeyId': self.api_key,
            'SignatureMethod': 'HmacSHA256',
            'SignatureVersion': '2',
            'Timestamp': timestamp
        }
        
        # 合并所有参数并排序
        all_params = dict(auth_params, **params)
        sorted_params = sorted(all_params.items(), key=lambda x: x[0])
        query_string = urllib.parse.urlencode(sorted_params)
        
        # 创建签名字符串 (注意换行符)
        pre_signed_text = f"{method}\napi.huobi.pro\n{endpoint}\n{query_string}"
        
        # 计算签名
        signature = base64.b64encode(
            hmac.new(
                self.api_secret.encode('utf-8'),
                pre_signed_text.encode('utf-8'),
                hashlib.sha256
            ).digest()
        ).decode('utf-8')
        
        return signature, timestamp, auth_params
    
    def get_account_id(self):
        """获取现货账户ID"""
        try:
            endpoint = "/v1/account/accounts"
            params = {}
            signature, timestamp, auth_params = self._create_signature("GET", endpoint, params)
            
            # 构建完整的URL参数
            final_params = dict(auth_params, **params)
            final_params['Signature'] = signature
            
            url = f"{self.base_url}{endpoint}"
            
            response = requests.get(url, params=final_params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('status') == 'ok':
                for account in data.get('data', []):
                    if account.get('type') == 'spot':
                        return account.get('id')
            
            logger.error(f"HTX account ID not found: {data}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting HTX account ID: {e}")
            return None
    
    def get_ticker_price(self, symbol):
        """获取交易对价格 (使用公开API)"""
        try:
            endpoint = f"/market/detail/merged"
            params = {'symbol': symbol.lower()}  # HTX使用小写
            
            url = f"{self.base_url}{endpoint}"
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('status') == 'ok':
                tick = data.get('tick', {})
                close_price = tick.get('close')
                if close_price:
                    logger.info(f"HTX {symbol} price: {close_price}")
                    return float(close_price)
            
            logger.error(f"HTX ticker request failed for {symbol}: {data}")
            return 1.0  # 如果获取失败，返回1.0避免计算错误
            
        except Exception as e:
            logger.error(f"Error getting HTX ticker for {symbol}: {e}")
            return 1.0  # 如果获取失败，返回1.0避免计算错误

    def get_account_balance(self, account_id):
        """获取账户余额"""
        try:
            endpoint = f"/v1/account/accounts/{account_id}/balance"
            params = {}
            signature, timestamp, auth_params = self._create_signature("GET", endpoint, params)
            
            # 构建完整的URL参数
            final_params = dict(auth_params, **params)
            final_params['Signature'] = signature
            
            url = f"{self.base_url}{endpoint}"
            
            response = requests.get(url, params=final_params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('status') == 'ok':
                balances = {}
                for item in data.get('data', {}).get('list', []):
                    currency = item.get('currency', '').upper()
                    balance_type = item.get('type', '')
                    balance_value = float(item.get('balance', 0))
                    
                    if currency not in balances:
                        balances[currency] = {'trade': 0, 'frozen': 0}
                    
                    if balance_type in ['trade', 'frozen']:
                        balances[currency][balance_type] = balance_value
                
                # 计算总余额
                total_balances = {}
                for currency, types in balances.items():
                    total = types['trade'] + types['frozen']
                    if total > 0:
                        total_balances[currency] = total
                
                return total_balances
            
            logger.error(f"HTX balance request failed: {data}")
            return {}
            
        except Exception as e:
            logger.error(f"Error getting HTX balance: {e}")
            return {}


class SimpleCollector:
    def __init__(self):
        self.load_config()
        self.setup_influxdb()
        self.setup_exchanges()
        
    def load_config(self):
        """加载配置文件"""
        with open('/app/config/config.yml', 'r') as f:
            self.config = yaml.safe_load(f)
        logger.info("Configuration loaded")
    
    def setup_influxdb(self):
        """设置InfluxDB连接"""
        influx_config = self.config['influxdb']
        self.influx_client = InfluxDBClient(
            url=f"http://{influx_config['host']}:{influx_config['port']}",
            token=influx_config['token'],
            org=influx_config['organization']
        )
        self.write_api = self.influx_client.write_api(write_options=SYNCHRONOUS)
        self.bucket = influx_config['bucket']
        self.org = influx_config['organization']
        logger.info("InfluxDB connected")
    
    def setup_exchanges(self):
        """设置交易所连接"""
        self.exchanges = {}
        
        # Binance and Binance2
        for exchange_name in ['binance', 'binance2']:
            if exchange_name in self.config['exchanges'] and self.config['exchanges'][exchange_name]['enabled']:
                try:
                    self.exchanges[exchange_name] = ccxt.binance({
                        'apiKey': self.config['exchanges'][exchange_name]['api_key'],
                        'secret': self.config['exchanges'][exchange_name]['api_secret'],
                        'sandbox': self.config['exchanges'][exchange_name]['sandbox'],
                        'enableRateLimit': True,
                    })
                    logger.info(f"{exchange_name} exchange initialized")
                except Exception as e:
                    logger.error(f"Failed to initialize {exchange_name}: {e}")
        
        # HTX - 使用直接API调用
        if self.config['exchanges']['htx']['enabled']:
            try:
                self.htx_api = HTXApi(
                    self.config['exchanges']['htx']['api_key'],
                    self.config['exchanges']['htx']['api_secret']
                )
                # 获取现货账户ID
                self.htx_account_id = self.htx_api.get_account_id()
                if self.htx_account_id:
                    logger.info(f"HTX exchange initialized with account ID: {self.htx_account_id}")
                else:
                    logger.error("Failed to get HTX account ID")
            except Exception as e:
                logger.error(f"Failed to initialize HTX: {e}")
                self.htx_api = None
    
    def get_account_balance_usdt(self, exchange_name, exchange=None):
        """获取账户USDT总价值"""
        try:
            # HTX使用直接API调用
            if exchange_name == 'htx':
                if not hasattr(self, 'htx_api') or not self.htx_api or not self.htx_account_id:
                    logger.error("HTX API not initialized")
                    return 0.0
                
                balance_data = self.htx_api.get_account_balance(self.htx_account_id)
                if not balance_data:
                    return 0.0
                
                # 详细记录HTX账户资产
                logger.info(f"HTX account assets: {balance_data}")
                
                total_usdt = 0.0
                for asset, amount in balance_data.items():
                    if amount > 0:
                        if asset == 'USDT':
                            total_usdt += amount
                            logger.info(f"HTX {asset}: {amount} (added to USDT total)")
                        elif asset == 'USDC':
                            # 获取USDC/USDT实时汇率
                            usdc_rate = self.htx_api.get_ticker_price('usdcusdt')
                            usdc_usdt_value = amount * usdc_rate
                            total_usdt += usdc_usdt_value
                            logger.info(f"HTX {asset}: {amount} * {usdc_rate} = {usdc_usdt_value} USDT")
                        elif asset == 'FDUSD':
                            # 获取FDUSD/USDT实时汇率
                            fdusd_rate = self.htx_api.get_ticker_price('fdusdusdt') 
                            fdusd_usdt_value = amount * fdusd_rate
                            total_usdt += fdusd_usdt_value
                            logger.info(f"HTX {asset}: {amount} * {fdusd_rate} = {fdusd_usdt_value} USDT")
                        else:
                            # 其他资产，数量很小可以忽略
                            if amount > 0.01:  # 只记录大于0.01的资产
                                logger.warning(f"HTX {asset}: {amount} (NOT counted in USDT - needs conversion)")
                
                logger.info(f"HTX total USDT value: {total_usdt}")
                return total_usdt
            
            else:
                # 其他交易所使用CCXT
                balance = exchange.fetch_balance()
                total_usdt = 0.0
                
                # 计算所有资产的USDT价值
                for asset, amount in balance['total'].items():
                    if amount > 0:
                        if asset == 'USDT':
                            total_usdt += amount
                            logger.info(f"Binance {asset}: {amount} (added to USDT total)")
                        elif asset == 'FDUSD':
                            # 获取FDUSD/USDT实时汇率
                            try:
                                fdusd_ticker = exchange.fetch_ticker('FDUSD/USDT')
                                fdusd_rate = fdusd_ticker['last']
                                fdusd_usdt_value = amount * fdusd_rate
                                total_usdt += fdusd_usdt_value
                                logger.info(f"Binance {asset}: {amount} * {fdusd_rate} = {fdusd_usdt_value} USDT")
                            except Exception as e:
                                logger.error(f"Failed to get FDUSD/USDT rate, using 1:1: {e}")
                                total_usdt += amount
                        elif asset == 'USDC':
                            # 获取USDC/USDT实时汇率
                            try:
                                usdc_ticker = exchange.fetch_ticker('USDC/USDT')
                                usdc_rate = usdc_ticker['last']
                                usdc_usdt_value = amount * usdc_rate
                                total_usdt += usdc_usdt_value
                                logger.info(f"Binance {asset}: {amount} * {usdc_rate} = {usdc_usdt_value} USDT")
                            except Exception as e:
                                logger.error(f"Failed to get USDC/USDT rate, using 1:1: {e}")
                                total_usdt += amount
                        else:
                            # 其他资产尝试获取对USDT的价格
                            try:
                                ticker_symbol = f"{asset}/USDT"
                                ticker = exchange.fetch_ticker(ticker_symbol)
                                asset_usdt_value = amount * ticker['last']
                                total_usdt += asset_usdt_value
                                logger.info(f"Binance {asset}: {amount} * {ticker['last']} = {asset_usdt_value} USDT")
                            except:
                                # 如果获取价格失败，忽略该资产
                                if amount > 0.01:  # 只记录大于0.01的资产
                                    logger.warning(f"Binance {asset}: {amount} (Could not get price)")
                                pass
                
                logger.info(f"Binance total USDT value: {total_usdt}")
                return total_usdt
            
        except Exception as e:
            logger.error(f"Error getting balance from {exchange_name}: {e}")
            return 0.0
    
    def write_balance_to_influx(self, exchange_name, balance_usdt):
        """写入余额数据到InfluxDB"""
        try:
            point = Point("strategy_pnl") \
                .tag("exchange", exchange_name) \
                .tag("strategy", "stablecoin_arbitrage") \
                .field("total_value_usdt", balance_usdt) \
                .time(datetime.utcnow())
            
            self.write_api.write(bucket=self.bucket, org=self.org, record=point)
            logger.info(f"Written to InfluxDB: {exchange_name} = ${balance_usdt:.2f}")
            
        except Exception as e:
            logger.error(f"Error writing to InfluxDB: {e}")
    
    def collect_once(self):
        """执行一次数据收集"""
        # 处理CCXT交易所
        for exchange_name, exchange in self.exchanges.items():
            balance_usdt = self.get_account_balance_usdt(exchange_name, exchange)
            if balance_usdt > 0:
                self.write_balance_to_influx(exchange_name, balance_usdt)
        
        # 处理HTX直接API
        if hasattr(self, 'htx_api') and self.htx_api and self.htx_account_id:
            balance_usdt = self.get_account_balance_usdt('htx')
            if balance_usdt > 0:
                self.write_balance_to_influx('htx', balance_usdt)
    
    def run(self):
        """主运行循环"""
        logger.info("Starting SCOA simple data collector")
        
        while True:
            try:
                self.collect_once()
                logger.info("Collection completed, sleeping 30 seconds...")
                time.sleep(30)
            except KeyboardInterrupt:
                logger.info("Stopping collector...")
                break
            except Exception as e:
                logger.error(f"Collection error: {e}")
                time.sleep(30)
        
        self.influx_client.close()
        logger.info("Collector stopped")


if __name__ == "__main__":
    # 设置日志
    logger.remove()
    logger.add(sys.stderr, level="INFO", format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {message}")
    
    collector = SimpleCollector()
    collector.run()