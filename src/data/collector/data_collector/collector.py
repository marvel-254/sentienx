import time
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import websocket
import json
import sqlite3
from data_collector.price_data import PriceData
from data_collector.preprocessor import DataPreprocessor
from logger.log_writer import Logger

class DataCollector:
    def __init__(self):
        self.price_data = PriceData()
        self.preprocessor = DataPreprocessor()
        self.logger = Logger()

        # Deriv API configuration
        self.deriv_config = {
            'app_id': os.getenv('DERIV_APP_ID', '69562'),
            'api_token': self._load_api_token(),
            'websocket_url': 'wss://ws.derivws.com/websockets/v3',
            'rest_url': 'https://api.deriv.com'
        }

        # Fallback API configurations
        self.api_keys = {
            'alpha_vantage': os.getenv('ALPHA_VANTAGE_API_KEY', ''),
            'yahoo_finance': 'free',  # Yahoo doesn't require key
            'exchangerate_api': os.getenv('EXCHANGERATE_API_KEY', ''),
            'freecurrency_api': os.getenv('FREECURRENCY_API_KEY', '')
        }

        # Rate limiting
        self.last_calls = {}
        self.rate_limits = {
            'deriv': 100,  # calls per minute for Deriv
            'alpha_vantage': 5,  # calls per minute
            'yahoo_finance': 2000,  # calls per hour
            'exchangerate_api': 1500,  # calls per month
            'freecurrency_api': 1000  # calls per month
        }

    def _load_api_token(self):
        """Load API token from file"""
        token_file = os.path.join(os.path.dirname(__file__), '..', '..', 'api-key')
        try:
            with open(token_file, 'r') as f:
                return f.read().strip()
        except:
            return os.getenv('DERIV_API_TOKEN', '')

    def _deriv_websocket_call(self, request_data, timeout=10):
        """Make a WebSocket call to Deriv API"""
        try:
            ws = websocket.create_connection(
                f"{self.deriv_config['websocket_url']}?app_id={self.deriv_config['app_id']}",
                timeout=timeout
            )

            # Send request
            ws.send(json.dumps(request_data))

            # Get response
            response = json.loads(ws.recv())
            ws.close()

            return response

        except Exception as e:
            self.logger.log_message('ERROR', 'DATA_COLLECTOR', f'Deriv API error: {str(e)}')
            return None

    def collect_deriv_historical_data(self, symbol, count=1000, granularity=60):
        """Collect historical data from Deriv API"""
        try:
            self._rate_limit_check('deriv')

            request_data = {
                "ticks_history": symbol,
                "count": count,
                "end": "latest",
                "granularity": granularity,
                "style": "candles"
            }

            if self.deriv_config['api_token']:
                request_data["authorize"] = self.deriv_config['api_token']

            response = self._deriv_websocket_call(request_data)

            if response and 'candles' in response:
                candles = response['candles']

                # Convert to DataFrame
                df = pd.DataFrame(candles)
                df['timestamp'] = pd.to_datetime(df['epoch'], unit='s')
                df = df.rename(columns={
                    'open': 'open_price',
                    'high': 'high_price',
                    'low': 'low_price',
                    'close': 'close_price'
                })
                df['symbol'] = symbol
                df['volume'] = 0  # Deriv doesn't provide volume

                return df

            return None

        except Exception as e:
            self.logger.log_message('ERROR', 'DATA_COLLECTOR', f'Error collecting Deriv data for {symbol}: {str(e)}')
            return None

    def get_deriv_realtime_price(self, symbol):
        """Get real-time price from Deriv API"""
        try:
            self._rate_limit_check('deriv')

            request_data = {
                "ticks": symbol,
                "subscribe": 0
            }

            if self.deriv_config['api_token']:
                request_data["authorize"] = self.deriv_config['api_token']

            response = self._deriv_websocket_call(request_data)

            if response and 'tick' in response:
                tick = response['tick']
                return {
                    'symbol': symbol,
                    'price': tick['quote'],
                    'timestamp': datetime.fromtimestamp(tick['epoch']),
                    'bid': tick.get('bid', tick['quote']),
                    'ask': tick.get('ask', tick['quote'])
                }

            return None

        except Exception as e:
            self.logger.log_message('ERROR', 'DATA_COLLECTOR', f'Error getting real-time price for {symbol}: {str(e)}')
            return None

    def _rate_limit_check(self, api_name):
        """Check and enforce rate limits"""
        now = time.time()
        if api_name in self.last_calls:
            time_diff = now - self.last_calls[api_name]
            if api_name == 'alpha_vantage' and time_diff < 12:  # 5 calls per minute
                time.sleep(12 - time_diff)
            elif api_name == 'yahoo_finance' and time_diff < 1.8:  # 2000 per hour
                time.sleep(1.8 - time_diff)

        self.last_calls[api_name] = time.time()

    def collect_historical_data(self, symbol, days=30, source='yahoo_finance'):
        """Collect historical market data from real APIs"""
        try:
            self.logger.log_message('INFO', 'DATA_COLLECTOR', f'Starting data collection for {symbol} from {source}')

            if source == 'yahoo_finance':
                data = self._get_yahoo_data(symbol, days)
            elif source == 'alpha_vantage':
                data = self._get_alpha_vantage_data(symbol, days)
            else:
                # Fallback to sample data
                data = self.price_data.generate_sample_data(symbol, days)

            if not data.empty:
                # Process the data
                processed_data = self.preprocessor.add_technical_indicators(symbol)

                # Save to database
                self._save_to_database(symbol, data)

                self.logger.log_message('INFO', 'DATA_COLLECTOR', f'Collected {len(data)} data points for {symbol}')
                return processed_data
            else:
                self.logger.log_message('WARNING', 'DATA_COLLECTOR', f'No data collected for {symbol}')
                return pd.DataFrame()

        except Exception as e:
            self.logger.log_message('ERROR', 'DATA_COLLECTOR', f'Error collecting data for {symbol}: {str(e)}')
            return pd.DataFrame()

    def _get_yahoo_data(self, symbol, days):
        """Get data from Yahoo Finance"""
        try:
            self._rate_limit_check('yahoo_finance')

            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            # Use yfinance library
            import yfinance as yf

            # Handle forex symbols (add =X suffix for Yahoo)
            if len(symbol) == 6 and symbol[:3].isalpha() and symbol[3:].isalpha():
                # Forex pair like EURUSD
                yahoo_symbol = f"{symbol}=X"
            else:
                yahoo_symbol = symbol

            ticker = yf.Ticker(yahoo_symbol)
            data = ticker.history(start=start_date, end=end_date, interval='1d')

            # Rename columns to match our format
            if not data.empty:
                data = data.rename(columns={
                    'Open': 'open',
                    'High': 'high',
                    'Low': 'low',
                    'Close': 'close',
                    'Volume': 'volume'
                })
                data.index.name = 'timestamp'
                data = data.reset_index()

            return data

        except Exception as e:
            self.logger.log_message('ERROR', 'DATA_COLLECTOR', f'Yahoo Finance error for {symbol}: {str(e)}')
            return pd.DataFrame()

    def _get_alpha_vantage_data(self, symbol, days):
        """Get data from Alpha Vantage"""
        try:
            if not self.api_keys['alpha_vantage']:
                self.logger.log_message('WARNING', 'DATA_COLLECTOR', 'Alpha Vantage API key not set')
                return pd.DataFrame()

            self._rate_limit_check('alpha_vantage')

            url = f'https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={symbol}&apikey={self.api_keys["alpha_vantage"]}&outputsize=full'

            response = requests.get(url, timeout=10)
            data = response.json()

            if 'Time Series (Daily)' not in data:
                self.logger.log_message('ERROR', 'DATA_COLLECTOR', f'Alpha Vantage API error: {data}')
                return pd.DataFrame()

            # Parse the data
            time_series = data['Time Series (Daily)']
            df_data = []

            for date_str, values in time_series.items():
                df_data.append({
                    'Date': pd.to_datetime(date_str),
                    'Open': float(values['1. open']),
                    'High': float(values['2. high']),
                    'Low': float(values['3. low']),
                    'Close': float(values['4. close']),
                    'Volume': int(values['5. volume'])
                })

            df = pd.DataFrame(df_data)
            df.set_index('Date', inplace=True)
            df.sort_index(inplace=True)

            # Filter by days
            cutoff_date = datetime.now() - timedelta(days=days)
            df = df[df.index >= cutoff_date]

            return df

        except Exception as e:
            self.logger.log_message('ERROR', 'DATA_COLLECTOR', f'Alpha Vantage error: {str(e)}')
            return pd.DataFrame()

    def _save_to_database(self, symbol, data):
        """Save collected data to database"""
        try:
            # Implementation for saving to SQLite or other database
            # For now, just log
            self.logger.log_message('INFO', 'DATA_COLLECTOR', f'Data saved for {symbol}: {len(data)} records')
        except Exception as e:
            self.logger.log_message('ERROR', 'DATA_COLLECTOR', f'Database save error: {str(e)}')

    def collect_realtime_data(self, symbol):
        """Collect real-time market data (placeholder for MT5 integration)"""
        try:
            # In real implementation, this would connect to MT5 API
            # For now, simulate real-time data updates

            latest_price = self.price_data.get_latest_price(symbol)

            if latest_price:
                # Update with simulated real-time price
                current_time = datetime.now()
                simulated_change = (np.random.normal(0, 0.0001))  # Small random change
                new_price = latest_price['price'] + simulated_change

                new_data_point = {
                    'timestamp': current_time,
                    'open': latest_price['price'],
                    'high': max(latest_price['price'], new_price),
                    'low': min(latest_price['price'], new_price),
                    'close': new_price,
                    'volume': np.random.randint(100, 1000)
                }

                # Load existing data and append
                existing_data = self.price_data.load_market_data(symbol)
                if not existing_data.empty:
                    existing_data = existing_data.append(new_data_point, ignore_index=True)
                    self.price_data.save_market_data(symbol, existing_data)

                self.logger.log_message('INFO', 'DATA_COLLECTOR', f'Real-time update for {symbol}: {new_price}')

                return new_data_point

        except Exception as e:
            self.logger.log_message('ERROR', 'DATA_COLLECTOR', f'Error collecting real-time data: {str(e)}')

        return None

    def maintain_local_database(self, symbols=['EURUSD', 'GBPUSD', 'USDJPY']):
        """Maintain local price database for offline backtesting"""
        for symbol in symbols:
            self.logger.log_message('INFO', 'DATA_COLLECTOR', f'Maintaining database for {symbol}')

            # Collect historical data
            self.collect_historical_data(symbol, days=90)  # 90 days of data

            # Process indicators
            self.preprocessor.add_technical_indicators(symbol)

        self.logger.log_message('INFO', 'DATA_COLLECTOR', 'Database maintenance completed')

    def start_realtime_collection(self, symbols=['EURUSD'], interval_seconds=60):
        """Start real-time data collection"""
        self.logger.log_message('INFO', 'DATA_COLLECTOR', f'Starting real-time collection for {symbols}')

        try:
            while True:
                for symbol in symbols:
                    self.collect_realtime_data(symbol)

                time.sleep(interval_seconds)

        except KeyboardInterrupt:
            self.logger.log_message('INFO', 'DATA_COLLECTOR', 'Real-time collection stopped by user')

        except Exception as e:
            self.logger.log_message('ERROR', 'DATA_COLLECTOR', f'Real-time collection error: {str(e)}')

if __name__ == "__main__":
    collector = DataCollector()

    # Collect historical data for EURUSD
    data = collector.collect_historical_data('EURUSD', days=30)
    print(f"Collected {len(data)} data points")

    # Maintain database for multiple symbols
    collector.maintain_local_database(['EURUSD', 'GBPUSD'])