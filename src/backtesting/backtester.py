"""
Backtesting Module for SENTIENX
Tests trading strategies on historical data
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from strategies.trading_strategies import StrategyManager, Signal
from trade_engine.broker_connector import TradingConnector
from logger.log_writer import Logger

class BacktestResult:
    def __init__(self):
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
        self.total_profit = 0.0
        self.total_loss = 0.0
        self.max_drawdown = 0.0
        self.win_rate = 0.0
        self.avg_win = 0.0
        self.avg_loss = 0.0
        self.profit_factor = 0.0
        self.sharpe_ratio = 0.0
        self.trades = []

    def calculate_metrics(self):
        """Calculate performance metrics"""
        if self.total_trades == 0:
            return

        self.win_rate = self.winning_trades / self.total_trades

        if self.winning_trades > 0:
            self.avg_win = self.total_profit / self.winning_trades

        if self.losing_trades > 0:
            self.avg_loss = self.total_loss / self.losing_trades

        if self.total_loss != 0:
            self.profit_factor = abs(self.total_profit / self.total_loss)
        else:
            self.profit_factor = float('inf')

        # Calculate Sharpe ratio (simplified)
        if len(self.trades) > 1:
            returns = [trade['profit_loss'] for trade in self.trades if trade['profit_loss'] != 0]
            if returns:
                avg_return = np.mean(returns)
                std_return = np.std(returns)
                if std_return != 0:
                    self.sharpe_ratio = avg_return / std_return * np.sqrt(252)  # Annualized

class Backtester:
    def __init__(self, initial_balance=1000.0, commission=0.0002, logger=None):
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.commission = commission  # Commission per lot (0.02%)
        self.logger = logger or Logger()
        self.broker = TradingConnector(logger)

    def backtest_strategy(self, strategy_name, symbol, start_date, end_date,
                         timeframe='H1', volume=0.01):
        """Backtest a trading strategy"""

        self.logger.log_message('INFO', 'BACKTESTER', f'Starting backtest for {strategy_name} on {symbol}')

        # Get historical data
        data = self.broker.get_historical_data(symbol, timeframe, start_date, end_date)

        if not data:
            self.logger.log_message('ERROR', 'BACKTESTER', 'No historical data available')
            return None

        # Convert to DataFrame
        df = pd.DataFrame(data)

        # Initialize strategy manager
        strategy_manager = StrategyManager(self.logger)
        if not strategy_manager.set_active_strategy(strategy_name):
            return None

        # Initialize result
        result = BacktestResult()
        self.current_balance = self.initial_balance

        # Track equity curve for drawdown calculation
        equity_curve = [self.initial_balance]

        # Simulate trading
        position = None  # {'type': 'BUY/SELL', 'entry_price': price, 'volume': vol}

        for i in range(len(df)):
            current_data = df.iloc[:i+1]  # All data up to current point

            if len(current_data) < 100:  # Need enough data for indicators
                continue

            # Get signal
            signal = strategy_manager.analyze_active_strategy(current_data)

            current_price = df.iloc[i]['close']

            # Process signals
            if isinstance(signal, dict):
                signal_type = signal['signal']
                confidence = signal.get('confidence', 0.5)
            else:
                signal_type = signal
                confidence = 0.5

            # Execute trades
            if signal_type == Signal.BUY and position is None:
                # Open buy position
                position = {
                    'type': 'BUY',
                    'entry_price': current_price,
                    'volume': volume,
                    'entry_time': df.iloc[i]['timestamp']
                }

            elif signal_type == Signal.SELL and position is None:
                # Open sell position
                position = {
                    'type': 'SELL',
                    'entry_price': current_price,
                    'volume': volume,
                    'entry_time': df.iloc[i]['timestamp']
                }

            elif position is not None:
                # Check for exit signals or opposite signals
                should_close = False

                if position['type'] == 'BUY':
                    if signal_type == Signal.SELL:
                        should_close = True
                else:  # SELL position
                    if signal_type == Signal.BUY:
                        should_close = True

                if should_close:
                    # Close position
                    exit_price = current_price
                    profit_loss = self._calculate_profit_loss(position, exit_price)

                    # Apply commission
                    commission_cost = (position['volume'] * 100000 * self.commission) * 2  # Round trip
                    profit_loss -= commission_cost

                    # Update balance
                    self.current_balance += profit_loss

                    # Record trade
                    trade = {
                        'entry_time': position['entry_time'],
                        'exit_time': df.iloc[i]['timestamp'],
                        'type': position['type'],
                        'entry_price': position['entry_price'],
                        'exit_price': exit_price,
                        'volume': position['volume'],
                        'profit_loss': profit_loss,
                        'commission': commission_cost,
                        'symbol': symbol
                    }

                    result.trades.append(trade)
                    result.total_trades += 1

                    if profit_loss > 0:
                        result.winning_trades += 1
                        result.total_profit += profit_loss
                    else:
                        result.losing_trades += 1
                        result.total_loss += profit_loss

                    position = None

            # Update equity curve
            equity_curve.append(self.current_balance)

        # Calculate drawdown
        result.max_drawdown = self._calculate_max_drawdown(equity_curve)

        # Calculate final metrics
        result.calculate_metrics()

        self.logger.log_message('INFO', 'BACKTESTER', f'Backtest completed: {result.total_trades} trades, '
                                                      f'Win rate: {result.win_rate:.2%}, '
                                                      f'Profit: ${result.total_profit:.2f}')

        return result

    def _calculate_profit_loss(self, position, exit_price):
        """Calculate profit/loss for a closed position"""
        if position['type'] == 'BUY':
            return (exit_price - position['entry_price']) * position['volume'] * 100000
        else:  # SELL
            return (position['entry_price'] - exit_price) * position['volume'] * 100000

    def _calculate_max_drawdown(self, equity_curve):
        """Calculate maximum drawdown from equity curve"""
        if not equity_curve:
            return 0.0

        peak = equity_curve[0]
        max_drawdown = 0.0

        for equity in equity_curve:
            if equity > peak:
                peak = equity
            drawdown = (peak - equity) / peak
            max_drawdown = max(max_drawdown, drawdown)

        return max_drawdown

    def compare_strategies(self, strategies, symbol, start_date, end_date):
        """Compare multiple strategies"""
        results = {}

        for strategy in strategies:
            result = self.backtest_strategy(strategy, symbol, start_date, end_date)
            if result:
                results[strategy] = result

        return results

    def print_backtest_report(self, result, strategy_name):
        """Print detailed backtest report"""
        print(f"\n{'='*50}")
        print(f"BACKTEST REPORT - {strategy_name}")
        print(f"{'='*50}")

        print(f"Total Trades: {result.total_trades}")
        print(f"Winning Trades: {result.winning_trades}")
        print(f"Losing Trades: {result.losing_trades}")
        print(".2%")
        print(".2f")
        print(".2f")
        print(".2f")
        print(".2f")
        print(".2f")
        print(".2f")
        print(".2f")

        if result.trades:
            print(f"\nFirst Trade: {result.trades[0]}")
            print(f"Last Trade: {result.trades[-1]}")

        print(f"{'='*50}")

class WalkForwardOptimizer:
    """Walk-forward optimization for strategy parameters"""

    def __init__(self, backtester):
        self.backtester = backtester
        self.logger = backtester.logger

    def optimize_parameters(self, strategy_base, symbol, start_date, end_date,
                          parameter_ranges, window_size_days=30):
        """Optimize strategy parameters using walk-forward analysis"""

        self.logger.log_message('INFO', 'WFO_OPTIMIZER', 'Starting walk-forward optimization')

        # Generate parameter combinations
        param_combinations = self._generate_param_combinations(parameter_ranges)

        best_params = None
        best_performance = -float('inf')

        current_date = start_date

        while current_date < end_date:
            train_end = current_date + timedelta(days=window_size_days)
            test_end = train_end + timedelta(days=window_size_days)

            if test_end > end_date:
                break

            # Optimize on training window
            best_local_params = self._optimize_window(strategy_base, symbol,
                                                    current_date, train_end,
                                                    param_combinations)

            # Test on next window
            if best_local_params:
                performance = self._test_parameters(strategy_base, symbol,
                                                  train_end, test_end,
                                                  best_local_params)

                if performance > best_performance:
                    best_performance = performance
                    best_params = best_local_params

            current_date = train_end

        self.logger.log_message('INFO', 'WFO_OPTIMIZER', f'Optimization completed. Best params: {best_params}')
        return best_params

    def _generate_param_combinations(self, parameter_ranges):
        """Generate all parameter combinations"""
        # Simplified - just return the ranges for now
        return [parameter_ranges]

    def _optimize_window(self, strategy_base, symbol, start_date, end_date, param_combinations):
        """Optimize parameters for a specific time window"""
        best_params = None
        best_performance = -float('inf')

        for params in param_combinations:
            # Test parameters
            performance = self._test_parameters(strategy_base, symbol, start_date, end_date, params)

            if performance > best_performance:
                best_performance = performance
                best_params = params

        return best_params

    def _test_parameters(self, strategy_base, symbol, start_date, end_date, params):
        """Test specific parameters and return performance metric"""
        # This would need to be implemented based on strategy type
        # For now, return a mock performance score
        return np.random.random()

if __name__ == "__main__":
    # Test backtester
    backtester = Backtester()

    # Run backtest
    start_date = datetime.now() - timedelta(days=30)
    end_date = datetime.now()

    result = backtester.backtest_strategy('tls', 'EURUSD', start_date, end_date)

    if result:
        backtester.print_backtest_report(result, 'TLS Strategy')

        # Compare strategies
        strategies = ['tls', 'ma_crossover', 'rsi_divergence']
        comparison = backtester.compare_strategies(strategies, 'EURUSD', start_date, end_date)

        print("\nSTRATEGY COMPARISON:")
        for strategy, res in comparison.items():
            print(f"{strategy}: {res.total_trades} trades, "
                  ".2%")