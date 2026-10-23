import time
from datetime import datetime, timedelta
from logger.log_writer import Logger
from ml_pipeline.neural_network import MLPipeline
from trade_engine.broker_connector import TradingConnector
from strategies.trading_strategies import StrategyManager, Signal

class TradeEngine:
    def __init__(self):
        self.logger = Logger()
        self.ml_pipeline = MLPipeline()
        self.broker = TradingConnector(self.logger)
        self.strategy_manager = StrategyManager(self.logger)
        self.active_trades = {}
        self.risk_management = RiskManagement()

    def analyze_market(self, symbol):
        """Analyze market conditions and generate trading signals"""
        try:
            # Get current market data for analysis
            current_price = self.broker.get_current_price(symbol)
            if not current_price:
                return None

            # Get recent historical data for technical analysis
            historical_data = self.mt5.get_historical_data(
                symbol, 'H1',
                datetime.now() - timedelta(hours=100),  # Last 100 hours
                datetime.now()
            )

            if not historical_data or len(historical_data) < 50:
                self.logger.log_message('WARNING', 'TRADE_ENGINE', 'Insufficient historical data for analysis')
                return None

            # Convert to DataFrame for analysis
            import pandas as pd
            df = pd.DataFrame(historical_data)

            # Use strategy manager for signal generation
            signal = self.strategy_manager.analyze_active_strategy(df)

            if signal and isinstance(signal, dict):
                signal_type = signal['signal']
                confidence = signal.get('confidence', 0.5)
            elif signal in [Signal.BUY, Signal.SELL]:
                signal_type = 'BUY' if signal == Signal.BUY else 'SELL'
                confidence = 0.5
            else:
                return None

            # Apply risk management checks
            trade_setup = {
                'symbol': symbol,
                'signal': signal_type,
                'confidence': confidence,
                'entry_price': current_price['bid'] if signal_type == 'BUY' else current_price['ask']
            }

            risk_check = self.risk_management.check_trade_risk(trade_setup)

            if risk_check['approved']:
                return {
                    'symbol': symbol,
                    'action': signal_type,
                    'confidence': confidence,
                    'entry_price': trade_setup['entry_price'],
                    'stop_loss': risk_check['stop_loss'],
                    'take_profit': risk_check['take_profit'],
                    'volume': risk_check['volume'],
                    'timestamp': datetime.now(),
                    'indicators': signal.get('indicators', {}) if isinstance(signal, dict) else {}
                }
            else:
                self.logger.log_message('INFO', 'TRADE_ENGINE', f'Trade rejected by risk management: {risk_check["reason"]}')

            return None

        except Exception as e:
            self.logger.log_message('ERROR', 'TRADE_ENGINE', f'Market analysis failed: {str(e)}')
            return None

    def execute_trade(self, trade_signal):
        """Execute a trade via broker API"""
        try:
            # Place order via broker API
            order_id = self.broker.place_market_order(
                symbol=trade_signal['symbol'],
                order_type=trade_signal['action'],
                volume=trade_signal['volume']
            )

            if not order_id:
                self.logger.log_message('ERROR', 'TRADE_ENGINE', 'Failed to place order via broker API')
                return None

            trade_data = {
                'id': str(order_id),
                'symbol': trade_signal['symbol'],
                'type': trade_signal['action'],
                'volume': trade_signal['volume'],
                'entry_price': trade_signal['entry_price'],
                'stop_loss': trade_signal['stop_loss'],
                'take_profit': trade_signal['take_profit'],
                'status': 'OPEN',
                'timestamp': trade_signal['timestamp'],
                'strategy': self.strategy_manager.active_strategy,
                'confidence': trade_signal.get('confidence', 0.5),
                'indicators': trade_signal.get('indicators', {})
            }

            # Log the trade
            self.logger.log_trade(trade_data)

            # Store active trade
            self.active_trades[str(order_id)] = trade_data

            self.logger.log_message('INFO', 'TRADE_ENGINE', f'Trade executed: {order_id} - {trade_signal["action"]} {trade_signal["volume"]} {trade_signal["symbol"]}')

            return str(order_id)

        except Exception as e:
            self.logger.log_message('ERROR', 'TRADE_ENGINE', f'Trade execution failed: {str(e)}')
            return None

    def monitor_trades(self):
        """Monitor active trades and close if conditions met"""
        try:
            for trade_id, trade in list(self.active_trades.items()):
                current_price = self.get_current_price(trade['symbol'])

                if current_price:
                    # Check stop loss
                    if trade['type'] == 'BUY' and current_price <= trade['stop_loss']:
                        self.close_trade(trade_id, current_price, 'STOP_LOSS')
                    elif trade['type'] == 'SELL' and current_price >= trade['stop_loss']:
                        self.close_trade(trade_id, current_price, 'STOP_LOSS')

                    # Check take profit
                    elif trade['type'] == 'BUY' and current_price >= trade['take_profit']:
                        self.close_trade(trade_id, current_price, 'TAKE_PROFIT')
                    elif trade['type'] == 'SELL' and current_price <= trade['take_profit']:
                        self.close_trade(trade_id, current_price, 'TAKE_PROFIT')

        except Exception as e:
            self.logger.log_message('ERROR', 'TRADE_ENGINE', f'Trade monitoring failed: {str(e)}')

    def close_trade(self, trade_id, exit_price, reason):
        """Close a trade"""
        try:
            if trade_id not in self.active_trades:
                return

            trade = self.active_trades[trade_id]

            # Calculate profit/loss
            if trade['type'] == 'BUY':
                profit_loss = (exit_price - trade['entry_price']) * trade['volume'] * 100000  # Assuming forex lot size
            else:
                profit_loss = (trade['entry_price'] - exit_price) * trade['volume'] * 100000

            # Update trade data
            trade.update({
                'exit_price': exit_price,
                'profit_loss': profit_loss,
                'status': 'CLOSED',
                'close_reason': reason,
                'close_timestamp': datetime.now()
            })

            # Log updated trade
            self.logger.log_trade(trade)

            # Remove from active trades
            del self.active_trades[trade_id]

            # Send reinforcement to ML pipeline
            self.ml_pipeline.reinforce_learning(trade)

            self.logger.log_message('INFO', 'TRADE_ENGINE', f'Trade closed: {trade_id}, P/L: {profit_loss:.2f}')

        except Exception as e:
            self.logger.log_message('ERROR', 'TRADE_ENGINE', f'Trade closure failed: {str(e)}')

    def get_current_price(self, symbol):
        """Get current market price from broker API"""
        price_data = self.broker.get_current_price(symbol)
        if price_data:
            return price_data['bid'] if price_data['bid'] else price_data['ask']
        return None

    def run_trading_loop(self, symbols=['EURUSD'], interval_seconds=300):  # 5 minutes
        """Main trading loop"""
        self.logger.log_message('INFO', 'TRADE_ENGINE', 'Starting trading loop')

        try:
            while True:
                for symbol in symbols:
                    # Analyze market
                    signal = self.analyze_market(symbol)

                    if signal:
                        # Execute trade
                        trade_id = self.execute_trade(signal)
                        if trade_id:
                            self.logger.log_message('INFO', 'TRADE_ENGINE', f'New trade opened: {trade_id}')

                    # Monitor existing trades
                    self.monitor_trades()

                time.sleep(interval_seconds)

        except KeyboardInterrupt:
            self.logger.log_message('INFO', 'TRADE_ENGINE', 'Trading loop stopped by user')

        except Exception as e:
            self.logger.log_message('ERROR', 'TRADE_ENGINE', f'Trading loop error: {str(e)}')

class RiskManagement:
    def __init__(self):
        self.max_risk_per_trade = 0.01  # 1% of account
        self.max_daily_loss = 10  # $10 max daily loss
        self.account_balance = 1000  # Starting balance

    def check_trade_risk(self, signal):
        """Check if trade meets risk management criteria"""
        try:
            current_price = signal.get('entry_price', 1.0)
            stop_loss_pips = abs(current_price - signal.get('stop_loss', current_price)) * 10000

            # Calculate position size based on risk
            risk_amount = self.account_balance * self.max_risk_per_trade
            pip_value = 0.1  # Standard lot pip value
            volume = risk_amount / (stop_loss_pips * pip_value)

            # Ensure volume is reasonable
            volume = min(volume, 0.1)  # Max 0.1 lots

            # Calculate actual stop loss and take profit
            if signal['signal'] == 'BUY':
                stop_loss = current_price - (stop_loss_pips / 10000)
                take_profit = current_price + (stop_loss_pips * 2 / 10000)  # 2:1 reward ratio
            else:
                stop_loss = current_price + (stop_loss_pips / 10000)
                take_profit = current_price - (stop_loss_pips * 2 / 10000)

            return {
                'approved': True,
                'volume': volume,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'risk_amount': risk_amount
            }

        except Exception as e:
            return {
                'approved': False,
                'reason': f'Risk calculation failed: {str(e)}'
            }

if __name__ == "__main__":
    engine = TradeEngine()

    # Test market analysis
    signal = engine.analyze_market('EURUSD')
    if signal:
        print(f"Generated signal: {signal}")

        # Test trade execution
        trade_id = engine.execute_trade(signal)
        if trade_id:
            print(f"Trade executed: {trade_id}")
    else:
        print("No signal generated")