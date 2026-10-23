# SENTIENX Live Trading Configuration
# Deriv API Configuration
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

DERIV_CONFIG = {
    'app_id': os.getenv('DERIV_APP_ID', 'YOUR_DERIV_APP_ID'),
    'api_token': os.getenv('DERIV_API_TOKEN', 'YOUR_DERIV_API_TOKEN'),
    'environment': os.getenv('DERIV_ENV', 'real'),
    'live_trading': True
}

# Risk Management Settings
RISK_CONFIG = {
    'max_risk_per_trade': 0.01,  # 1% of account balance
    'max_daily_loss': 10,        # $10 maximum daily loss
    'default_volume': 0.01,      # Default position size
    'max_open_positions': 3      # Maximum concurrent positions
}

# Trading Settings
TRADING_CONFIG = {
    'symbols': ['EUR/USD', 'GBP/USD', 'USD/JPY'],
    'default_strategy': 'tls',
    'auto_trading': True,       # Set to True for automated trading
    'confidence_threshold': 0.7  # Minimum confidence for trades
}