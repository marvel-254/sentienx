#!/usr/bin/env python3
"""
SENTIENX Real-Time Trading Bot
Executes live trades on Deriv with real account balance
"""

import sys
import os
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import DERIV_CONFIG, RISK_CONFIG, TRADING_CONFIG
from logger.log_writer import Logger
from trade_engine.broker_connector import TradingConnector
from trade_engine.main import TradeEngine
from strategies.trading_strategies import StrategyManager
from ml_pipeline.neural_network import MLPipeline

logging.basicConfig(level=logging.INFO)
logger_instance = Logger()


class RealTimeTradingBot:
    """Real-time trading bot using live Deriv account"""
    
    def __init__(self):
        self.broker = TradingConnector(logger_instance)
        self.trade_engine = TradeEngine()
        self.strategy_manager = StrategyManager(logger_instance)
        self.ml_pipeline = MLPipeline()
        self.running = False
        self.trading_symbols = TRADING_CONFIG['symbols']
        self.confidence_threshold = TRADING_CONFIG['confidence_threshold']
        self.auto_trading_enabled = TRADING_CONFIG['auto_trading']
        
        logger_instance.log_message('INFO', 'BOT_INIT', 'SENTIENX Trading Bot initialized')
    
    def connect_to_deriv(self) -> bool:
        """Connect to real Deriv account"""
        try:
            logger_instance.log_message('INFO', 'BOT_CONNECT', 'Connecting to Deriv with real account')
            
            if not self.broker.configure_deriv(
                app_id=DERIV_CONFIG['app_id'],
                api_token=DERIV_CONFIG['api_token'],
                environment=DERIV_CONFIG['environment']
            ):
                logger_instance.log_message('ERROR', 'BOT_CONNECT', 'Failed to configure Deriv')
                return False
            
            if not self.broker.connect():
                logger_instance.log_message('ERROR', 'BOT_CONNECT', 'Failed to connect to Deriv')
                return False
            
            account_info = self.broker.get_account_info()
            if account_info:
                logger_instance.log_message(
                    'INFO', 'BOT_CONNECT',
                    f'Connected to Deriv. Balance: {account_info.get("balance", 0)}'
                )
                return True
            
            return False
        
        except Exception as e:
            logger_instance.log_message('ERROR', 'BOT_CONNECT', f'Connection error: {str(e)}')
            return False
    
    def analyze_market(self, symbol: str) -> dict:
        """Analyze market and generate trading signal"""
        try:
            historical_data = self.broker.get_historical_data(symbol, 'H1', None, None)
            
            if not historical_data or len(historical_data) < 50:
                logger_instance.log_message('WARNING', 'BOT_ANALYSIS', f'Insufficient data for {symbol}')
                return {}
            
            import pandas as pd
            df = pd.DataFrame(historical_data)
            
            signal_result = self.strategy_manager.analyze_active_strategy(df)
            
            if not signal_result:
                return {}
            
            confidence = signal_result.get('confidence', 0.5)
            
            if confidence >= self.confidence_threshold:
                return {
                    'symbol': symbol,
                    'signal': signal_result.get('signal', 'HOLD'),
                    'confidence': confidence,
                    'timestamp': datetime.now(),
                    'indicators': signal_result.get('indicators', {})
                }
            
            return {}
        
        except Exception as e:
            logger_instance.log_message('ERROR', 'BOT_ANALYSIS', f'Analysis error for {symbol}: {str(e)}')
            return {}
    
    def execute_trade(self, analysis: dict) -> bool:
        """Execute trade based on analysis"""
        try:
            if not analysis or not self.auto_trading_enabled:
                return False
            
            symbol = analysis.get('symbol')
            signal = analysis.get('signal')
            confidence = analysis.get('confidence', 0)
            
            current_price = self.broker.get_current_price(symbol)
            if not current_price:
                return False
            
            volume = RISK_CONFIG.get('default_volume', 0.01)
            
            order_id = self.broker.place_market_order(
                symbol=symbol,
                order_type=signal,
                volume=volume,
                comment=f"SENTIENX_{signal}_{confidence:.2f}"
            )
            
            if order_id:
                logger_instance.log_message(
                    'INFO', 'BOT_TRADE',
                    f'Trade executed: {signal} {volume} {symbol} at {current_price.get("bid")}'
                )
                return True
            
            return False
        
        except Exception as e:
            logger_instance.log_message('ERROR', 'BOT_TRADE', f'Trade execution error: {str(e)}')
            return False
    
    def run(self, check_interval: int = 60):
        """Main trading loop"""
        self.running = True
        logger_instance.log_message('INFO', 'BOT_RUN', 'Trading bot started')
        
        try:
            while self.running:
                try:
                    account_info = self.broker.get_account_info()
                    if account_info:
                        logger_instance.log_message(
                            'INFO', 'BOT_STATUS',
                            f'Account Balance: {account_info.get("balance", 0)}'
                        )
                    
                    for symbol in self.trading_symbols:
                        analysis = self.analyze_market(symbol)
                        
                        if analysis:
                            self.execute_trade(analysis)
                    
                    logger_instance.log_message('INFO', 'BOT_CYCLE', 'Analysis cycle completed')
                    
                    time.sleep(check_interval)
                
                except KeyboardInterrupt:
                    logger_instance.log_message('INFO', 'BOT_RUN', 'Received interrupt signal')
                    break
                
                except Exception as e:
                    logger_instance.log_message('ERROR', 'BOT_RUN', f'Cycle error: {str(e)}')
                    time.sleep(5)
        
        finally:
            self.stop()
    
    def stop(self):
        """Stop the trading bot"""
        self.running = False
        self.broker.disconnect()
        logger_instance.log_message('INFO', 'BOT_STOP', 'Trading bot stopped')


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='SENTIENX Real-Time Trading Bot')
    parser.add_argument('--interval', type=int, default=60, help='Check interval in seconds')
    parser.add_argument('--symbols', nargs='+', help='Trading symbols')
    args = parser.parse_args()
    
    if args.symbols:
        TRADING_CONFIG['symbols'] = args.symbols
    
    bot = RealTimeTradingBot()
    
    if bot.connect_to_deriv():
        bot.run(check_interval=args.interval)
    else:
        logger_instance.log_message('ERROR', 'BOT_MAIN', 'Failed to connect to Deriv')
        sys.exit(1)


if __name__ == '__main__':
    main()
