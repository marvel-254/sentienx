"""
Trading Connector for SENTIENX
Real Deriv API Integration
"""

import requests
import json
import time
from datetime import datetime, timedelta
from logger.log_writer import Logger
from api.services.deriv_service import DerivService, RateLimiter

class BrokerAPIConnector:
    """Base class for broker API connectors"""

    def __init__(self, logger=None):
        self.logger = logger or Logger()
        self.session = requests.Session()
        self.connected = False
        self.account_info = None

    def connect(self):
        """Connect to broker API"""
        raise NotImplementedError

    def get_account_info(self):
        """Get account information"""
        raise NotImplementedError

    def get_market_data(self, symbol, timeframe='H1', count=100):
        """Get historical market data"""
        raise NotImplementedError

    def place_order(self, symbol, order_type, volume, price=None):
        """Place a trading order"""
        raise NotImplementedError

    def close_position(self, ticket):
        """Close a position"""
        raise NotImplementedError

    def get_positions(self):
        """Get open positions"""
        raise NotImplementedError

class OANDAConnector(BrokerAPIConnector):
    """OANDA Broker API Connector"""

    def __init__(self, api_key=None, account_id=None, logger=None, demo=True):
        super().__init__(logger)
        self.api_key = api_key
        self.account_id = account_id
        self.base_url = "https://api-fxpractice.oanda.com" if demo else "https://api-fxtrade.oanda.com"
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        })

    def connect(self):
        """Connect to OANDA API"""
        try:
            response = self.session.get(f"{self.base_url}/v3/accounts/{self.account_id}")
            if response.status_code == 200:
                self.account_info = response.json()['account']
                self.connected = True
                self.logger.log_message('INFO', 'OANDA_CONNECTOR', f'Connected to OANDA account {self.account_id}')
                return True
            else:
                self.logger.log_message('ERROR', 'OANDA_CONNECTOR', f'Failed to connect: {response.text}')
                return False
        except Exception as e:
            self.logger.log_message('ERROR', 'OANDA_CONNECTOR', f'Connection error: {str(e)}')
            return False

    def get_account_info(self):
        """Get account information"""
        if not self.connected:
            return None
        return self.account_info

    def get_market_data(self, symbol, timeframe='H1', count=100):
        """Get historical market data from OANDA"""
        try:
            # Convert timeframe to OANDA format
            granularity_map = {
                'M1': 'M1', 'M5': 'M5', 'M15': 'M15', 'M30': 'M30',
                'H1': 'H1', 'H4': 'H4', 'D1': 'D', 'W1': 'W', 'M1': 'M'
            }
            granularity = granularity_map.get(timeframe, 'H1')

            params = {
                'granularity': granularity,
                'count': count
            }

            response = self.session.get(f"{self.base_url}/v3/instruments/{symbol}/candles", params=params)

            if response.status_code == 200:
                data = response.json()
                candles = data.get('candles', [])

                # Convert to our format
                market_data = []
                for candle in candles:
                    if candle.get('complete'):
                        market_data.append({
                            'timestamp': candle['time'],
                            'open': float(candle['mid']['o']),
                            'high': float(candle['mid']['h']),
                            'low': float(candle['mid']['l']),
                            'close': float(candle['mid']['c']),
                            'volume': candle.get('volume', 0)
                        })

                self.logger.log_message('INFO', 'OANDA_CONNECTOR', f'Retrieved {len(market_data)} candles for {symbol}')
                return market_data
            else:
                self.logger.log_message('ERROR', 'OANDA_CONNECTOR', f'Failed to get market data: {response.text}')
                return []

        except Exception as e:
            self.logger.log_message('ERROR', 'OANDA_CONNECTOR', f'Error getting market data: {str(e)}')
            return []

    def place_order(self, symbol, order_type, volume, price=None):
        """Place an order with OANDA"""
        try:
            order_data = {
                "order": {
                    "instrument": symbol,
                    "units": volume if order_type == 'BUY' else -volume,
                    "type": "MARKET",
                    "timeInForce": "FOK"
                }
            }

            response = self.session.post(
                f"{self.base_url}/v3/accounts/{self.account_id}/orders",
                json=order_data
            )

            if response.status_code == 201:
                order_result = response.json()
                order_id = order_result['orderCreateTransaction']['id']
                self.logger.log_message('INFO', 'OANDA_CONNECTOR', f'Order placed: {order_id} - {order_type} {volume} {symbol}')
                return order_id
            else:
                self.logger.log_message('ERROR', 'OANDA_CONNECTOR', f'Order failed: {response.text}')
                return None

        except Exception as e:
            self.logger.log_message('ERROR', 'OANDA_CONNECTOR', f'Error placing order: {str(e)}')
            return None

    def close_position(self, ticket):
        """Close a position"""
        try:
            # For OANDA, we need to close by instrument
            # This is a simplified version - in practice you'd need to get position details first
            close_data = {
                "longUnits": "ALL",
                "shortUnits": "ALL"
            }

            response = self.session.put(
                f"{self.base_url}/v3/accounts/{self.account_id}/positions/{ticket}/close",
                json=close_data
            )

            if response.status_code == 200:
                self.logger.log_message('INFO', 'OANDA_CONNECTOR', f'Position closed: {ticket}')
                return response.json()
            else:
                self.logger.log_message('ERROR', 'OANDA_CONNECTOR', f'Close failed: {response.text}')
                return None

        except Exception as e:
            self.logger.log_message('ERROR', 'OANDA_CONNECTOR', f'Error closing position: {str(e)}')
            return None

    def get_positions(self):
        """Get open positions"""
        try:
            response = self.session.get(f"{self.base_url}/v3/accounts/{self.account_id}/openPositions")

            if response.status_code == 200:
                positions_data = response.json()
                positions = positions_data.get('positions', [])
                return positions
            else:
                self.logger.log_message('ERROR', 'OANDA_CONNECTOR', f'Failed to get positions: {response.text}')
                return []

        except Exception as e:
            self.logger.log_message('ERROR', 'OANDA_CONNECTOR', f'Error getting positions: {str(e)}')
            return []

class TradingConnector:
    """Main trading connector using Deriv API"""

    def __init__(self, logger=None):
        self.logger = logger or Logger()
        self.deriv_service = None
        self.connected = False
        self.rate_limiter = RateLimiter(calls_per_second=5)

    def configure_deriv(self, app_id: str, api_token: str, environment: str = "real"):
        """Configure Deriv connection"""
        try:
            self.deriv_service = DerivService(app_id, api_token, environment)
            if self.deriv_service.connect():
                self.connected = True
                self.logger.log_message('INFO', 'TRADING_CONNECTOR', 'Configured for Deriv API (Real Trading)')
                return True
            else:
                self.logger.log_message('ERROR', 'TRADING_CONNECTOR', 'Failed to connect to Deriv')
                return False
        except Exception as e:
            self.logger.log_message('ERROR', 'TRADING_CONNECTOR', f'Deriv configuration failed: {str(e)}')
            return False

    def connect(self):
        """Connect to Deriv broker"""
        if not self.deriv_service:
            self.logger.log_message('ERROR', 'TRADING_CONNECTOR', 'Deriv service not configured')
            return False
        return self.connected

    def get_account_info(self):
        """Get account information from Deriv"""
        if not self.connected or not self.deriv_service:
            return None
        
        self.rate_limiter.wait()
        return self.deriv_service.get_account_balance()

    def get_current_price(self, symbol):
        """Get current market price"""
        if not self.connected or not self.deriv_service:
            return None
        
        self.rate_limiter.wait()
        data = self.deriv_service.get_market_data(symbol, "1m", 1)
        
        if data and len(data) > 0:
            latest = data[-1]
            return {
                'symbol': symbol,
                'bid': latest.get('close', 0),
                'ask': latest.get('close', 0) + 0.0001,
                'timestamp': datetime.now()
            }
        return None

    def get_historical_data(self, symbol, timeframe='H1', start_date=None, end_date=None):
        """Get historical market data from Deriv"""
        if not self.connected or not self.deriv_service:
            return []
        
        self.rate_limiter.wait()
        return self.deriv_service.get_market_data(symbol, timeframe, 500) or []

    def place_market_order(self, symbol, order_type, volume, comment="SENTIENX"):
        """Place a market order on Deriv"""
        if not self.connected or not self.deriv_service:
            self.logger.log_message('ERROR', 'TRADING_CONNECTOR', 'Not connected to Deriv')
            return None
        
        self.rate_limiter.wait()
        
        try:
            if order_type.upper() == 'BUY':
                result = self.deriv_service.place_buy_order(symbol, volume)
            else:
                result = self.deriv_service.place_sell_order(symbol, volume)
            
            if result:
                self.logger.log_message('INFO', 'TRADING_CONNECTOR', 
                                      f'Order placed on Deriv: {order_type} {volume} {symbol}')
                return result.get('order_id')
            return None
        except Exception as e:
            self.logger.log_message('ERROR', 'TRADING_CONNECTOR', f'Failed to place order: {str(e)}')
            return None

    def close_position(self, ticket, volume=None):
        """Close a position on Deriv"""
        if not self.connected or not self.deriv_service:
            return None
        
        self.rate_limiter.wait()
        
        try:
            result = self.deriv_service.close_position(str(ticket))
            if result:
                self.logger.log_message('INFO', 'TRADING_CONNECTOR', f'Position closed on Deriv: {ticket}')
            return result
        except Exception as e:
            self.logger.log_message('ERROR', 'TRADING_CONNECTOR', f'Failed to close position: {str(e)}')
            return None

    def get_open_positions(self):
        """Get all open positions from Deriv"""
        if not self.connected or not self.deriv_service:
            return []
        
        self.rate_limiter.wait()
        positions = self.deriv_service.get_open_positions() or []
        return positions

    def disconnect(self):
        """Disconnect from Deriv"""
        if self.deriv_service:
            self.deriv_service.disconnect()
            self.connected = False
            self.logger.log_message('INFO', 'TRADING_CONNECTOR', 'Disconnected from Deriv')

if __name__ == "__main__":
    # Test the connector
    connector = TradingConnector()

    # Test mock mode
    print("Testing mock mode...")
    price = connector.get_current_price('EURUSD')
    print(f"EURUSD Price: {price}")

    historical = connector.get_historical_data('EURUSD', 'H1')
    print(f"Historical data points: {len(historical)}")

    # Test OANDA configuration (would need real credentials)
    # connector.configure_oanda('your_api_key', 'your_account_id', demo=True)
    # connector.connect()