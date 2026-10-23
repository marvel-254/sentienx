"""
Deriv Market Integration Service
Handles live market data streaming and trading execution
"""

import json
import time
import requests
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
import threading
from pathlib import Path

logger = logging.getLogger(__name__)


class DerivService:
    """Deriv API service for live trading"""
    
    def __init__(self, app_id: str, api_token: str, environment: str = "real"):
        self.app_id = app_id
        self.api_token = api_token
        self.environment = environment
        self.base_url = "wss://ws.deriv.com"
        self.account_id = None
        self.connected = False
        self.session = requests.Session()
        self.rate_limiter = RateLimiter(calls_per_second=5)
        
    def connect(self) -> bool:
        """Establish connection to Deriv API"""
        try:
            logger.info("Connecting to Deriv API")
            self.connected = True
            self.account_id = self._get_account_info()
            logger.info(f"Connected successfully. Account: {self.account_id}")
            return True
        except Exception as e:
            logger.error(f"Connection failed: {str(e)}")
            self.connected = False
            return False
    
    def get_account_balance(self) -> Optional[Dict[str, Any]]:
        """Get current account balance and info"""
        if not self.connected:
            return None
        
        try:
            self.rate_limiter.wait()
            
            endpoint = "https://api.deriv.com/api/v3"
            headers = {
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json"
            }
            
            response = self.session.get(
                f"{endpoint}/balance",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'balance': data.get('balance', 0),
                    'equity': data.get('equity', 0),
                    'free_margin': data.get('free_margin', 0),
                    'margin_level': data.get('margin_level', 0),
                    'currency': data.get('currency', 'USD')
                }
        except Exception as e:
            logger.error(f"Failed to get balance: {str(e)}")
        
        return None
    
    def get_market_data(self, symbol: str, timeframe: str = "1m", count: int = 100) -> Optional[List[Dict]]:
        """Get historical market data"""
        if not self.connected:
            return None
        
        try:
            self.rate_limiter.wait()
            
            endpoint = "https://api.deriv.com/api/v3"
            headers = {
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json"
            }
            
            timeframe_map = {
                "1m": 60,
                "5m": 300,
                "15m": 900,
                "1h": 3600,
                "1d": 86400
            }
            
            params = {
                'symbol': symbol,
                'granularity': timeframe_map.get(timeframe, 60),
                'count': count
            }
            
            response = self.session.get(
                f"{endpoint}/ticks",
                headers=headers,
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json().get('ticks', [])
        
        except Exception as e:
            logger.error(f"Failed to get market data: {str(e)}")
        
        return None
    
    def place_buy_order(self, symbol: str, amount: float, price: Optional[float] = None) -> Optional[Dict]:
        """Place a buy order"""
        return self._place_order(symbol, "buy", amount, price)
    
    def place_sell_order(self, symbol: str, amount: float, price: Optional[float] = None) -> Optional[Dict]:
        """Place a sell order"""
        return self._place_order(symbol, "sell", amount, price)
    
    def _place_order(self, symbol: str, order_type: str, amount: float, price: Optional[float] = None) -> Optional[Dict]:
        """Place a trading order"""
        if not self.connected:
            logger.warning("Not connected to Deriv API")
            return None
        
        try:
            self.rate_limiter.wait()
            
            endpoint = "https://api.deriv.com/api/v3"
            headers = {
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json"
            }
            
            order_data = {
                'symbol': symbol,
                'side': order_type.lower(),
                'quantity': amount,
                'type': 'market' if price is None else 'limit'
            }
            
            if price:
                order_data['price'] = price
            
            response = self.session.post(
                f"{endpoint}/orders",
                headers=headers,
                json=order_data,
                timeout=10
            )
            
            if response.status_code in [200, 201]:
                result = response.json()
                logger.info(f"Order placed: {result}")
                return result
            else:
                logger.error(f"Order failed: {response.text}")
        
        except Exception as e:
            logger.error(f"Failed to place order: {str(e)}")
        
        return None
    
    def close_position(self, position_id: str) -> bool:
        """Close an open position"""
        if not self.connected:
            return False
        
        try:
            self.rate_limiter.wait()
            
            endpoint = "https://api.deriv.com/api/v3"
            headers = {
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json"
            }
            
            response = self.session.delete(
                f"{endpoint}/positions/{position_id}",
                headers=headers,
                timeout=10
            )
            
            return response.status_code in [200, 204]
        
        except Exception as e:
            logger.error(f"Failed to close position: {str(e)}")
            return False
    
    def get_open_positions(self) -> Optional[List[Dict]]:
        """Get all open positions"""
        if not self.connected:
            return None
        
        try:
            self.rate_limiter.wait()
            
            endpoint = "https://api.deriv.com/api/v3"
            headers = {
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json"
            }
            
            response = self.session.get(
                f"{endpoint}/positions",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json().get('positions', [])
        
        except Exception as e:
            logger.error(f"Failed to get positions: {str(e)}")
        
        return None
    
    def _get_account_info(self) -> Optional[str]:
        """Get account information"""
        try:
            self.rate_limiter.wait()
            
            endpoint = "https://api.deriv.com/api/v3"
            headers = {
                "Authorization": f"Bearer {self.api_token}",
                "Content-Type": "application/json"
            }
            
            response = self.session.get(
                f"{endpoint}/account",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json().get('account_id')
        
        except Exception as e:
            logger.error(f"Failed to get account info: {str(e)}")
        
        return None
    
    def disconnect(self):
        """Disconnect from Deriv API"""
        self.connected = False
        logger.info("Disconnected from Deriv API")


class RateLimiter:
    """Rate limiter to prevent API flagging"""
    
    def __init__(self, calls_per_second: int = 5):
        self.calls_per_second = calls_per_second
        self.min_interval = 1.0 / calls_per_second
        self.last_call = 0
        self.lock = threading.Lock()
    
    def wait(self):
        """Wait to respect rate limit"""
        with self.lock:
            now = time.time()
            elapsed = now - self.last_call
            
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            
            self.last_call = time.time()


class DerivConnectionPool:
    """Manage multiple Deriv API connections efficiently"""
    
    def __init__(self, app_id: str, api_token: str, pool_size: int = 3):
        self.app_id = app_id
        self.api_token = api_token
        self.pool_size = pool_size
        self.connections = []
        self.current_index = 0
        self.lock = threading.Lock()
        
        self._initialize_pool()
    
    def _initialize_pool(self):
        """Initialize connection pool"""
        for _ in range(self.pool_size):
            conn = DerivService(self.app_id, self.api_token)
            if conn.connect():
                self.connections.append(conn)
        
        logger.info(f"Connection pool initialized with {len(self.connections)} connections")
    
    def get_connection(self) -> Optional[DerivService]:
        """Get next available connection from pool"""
        with self.lock:
            if not self.connections:
                return None
            
            conn = self.connections[self.current_index]
            self.current_index = (self.current_index + 1) % len(self.connections)
            
            return conn
    
    def close_all(self):
        """Close all connections in pool"""
        for conn in self.connections:
            conn.disconnect()
        self.connections.clear()
