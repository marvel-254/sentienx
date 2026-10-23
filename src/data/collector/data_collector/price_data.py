import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import json

class PriceData:
    def __init__(self, data_dir='data'):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)

    def save_market_data(self, symbol, data):
        """Save market data to JSON file"""
        filepath = os.path.join(self.data_dir, f'{symbol}_data.json')

        # Convert data to list of dicts if it's a DataFrame
        if isinstance(data, pd.DataFrame):
            data_dict = data.to_dict('records')
        else:
            data_dict = data

        with open(filepath, 'w') as f:
            json.dump(data_dict, f, indent=2, default=str)

    def load_market_data(self, symbol):
        """Load market data from JSON file"""
        filepath = os.path.join(self.data_dir, f'{symbol}_data.json')

        if not os.path.exists(filepath):
            return pd.DataFrame()

        with open(filepath, 'r') as f:
            data = json.load(f)

        return pd.DataFrame(data)

    def generate_sample_data(self, symbol, days=30):
        """Generate sample market data for testing"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        dates = pd.date_range(start=start_date, end=end_date, freq='1H')

        # Generate realistic price movements
        np.random.seed(42)  # For reproducible results

        # Start with a base price (example for EURUSD)
        base_price = 1.0850 if symbol == 'EURUSD' else 1.2750

        prices = []
        current_price = base_price

        for i in range(len(dates)):
            # Random walk with some trend
            change = np.random.normal(0, 0.001)  # Small random changes
            current_price += change

            # Generate OHLC data
            high = current_price + abs(np.random.normal(0, 0.0005))
            low = current_price - abs(np.random.normal(0, 0.0005))
            open_price = current_price
            close = current_price + np.random.normal(0, 0.0002)
            volume = np.random.randint(1000, 10000)

            prices.append({
                'timestamp': dates[i],
                'open': round(open_price, 5),
                'high': round(high, 5),
                'low': round(low, 5),
                'close': round(close, 5),
                'volume': volume
            })

            current_price = close

        df = pd.DataFrame(prices)
        self.save_market_data(symbol, df)
        return df

    def get_latest_price(self, symbol):
        """Get the latest price for a symbol"""
        df = self.load_market_data(symbol)
        if df.empty:
            return None

        latest = df.iloc[-1]
        return {
            'symbol': symbol,
            'price': latest['close'],
            'timestamp': latest['timestamp']
        }

if __name__ == "__main__":
    pd_obj = PriceData()

    # Generate sample data for EURUSD
    data = pd_obj.generate_sample_data('EURUSD', days=7)
    print(f"Generated {len(data)} data points for EURUSD")

    # Get latest price
    latest = pd_obj.get_latest_price('EURUSD')
    print(f"Latest EURUSD price: {latest}")