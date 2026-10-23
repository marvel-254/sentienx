#!/usr/bin/env python3
"""
SENTIENX - Hybrid AI Trading System
Main entry point for the trading system
"""

import sys
import os
import argparse
from datetime import datetime

# Add sentienx to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from data_collector.collector import DataCollector
from logger.log_summary import LogSummary
from trade_engine.main import TradeEngine
from ml_pipeline.neural_network import MLPipeline
from backtesting.backtester import Backtester
from strategies.trading_strategies import StrategyManager

class SENTIENX:
    def __init__(self):
        self.data_collector = DataCollector()
        self.log_summary = LogSummary()
        self.trade_engine = TradeEngine()
        self.ml_pipeline = MLPipeline()
        self.backtester = Backtester()
        self.strategy_manager = StrategyManager()

        print("SENTIENX initialized successfully")
        print("=" * 50)

    def setup_system(self):
        """Initial system setup"""
        print("Setting up SENTIENX system...")

        # Create necessary directories
        os.makedirs('data', exist_ok=True)
        os.makedirs('models', exist_ok=True)

        # Collect initial data
        print("Collecting initial market data...")
        self.data_collector.maintain_local_database(['EURUSD', 'GBPUSD', 'USDJPY'])

        # Train initial model
        print("Training initial ML model...")
        result = self.ml_pipeline.train_model('EURUSD')
        if result:
            print(f"Model trained with accuracy: {result['accuracy']:.4f}")
        else:
            print("Model training failed")

        print("System setup completed")

    def run_training_mode(self):
        """Run in training mode"""
        print("Starting SENTIENX in TRAINING mode...")
        print("Press Ctrl+C to stop")

        try:
            while True:
                # Collect new data
                self.data_collector.collect_realtime_data('EURUSD')

                # Retrain model periodically
                result = self.ml_pipeline.train_model('EURUSD')
                if result:
                    print(f"Model retrained with accuracy: {result['accuracy']:.4f}")
                # Show summary
                self.log_summary.display_trade_summary()

                # Wait before next iteration
                import time
                time.sleep(3600)  # Retrain every hour

        except KeyboardInterrupt:
            print("\nTraining mode stopped")

    def run_trading_mode(self):
        """Run in live trading mode"""
        print("Starting SENTIENX in TRADING mode...")
        print("WARNING: This will execute real trades!")
        print("Press Ctrl+C to stop")

        try:
            self.trade_engine.run_trading_loop(['EURUSD'])

        except KeyboardInterrupt:
            print("\nTrading mode stopped")

    def run_demo_mode(self):
        """Run in demo mode (paper trading)"""
        print("Starting SENTIENX in DEMO mode...")
        print("This is paper trading - no real money at risk")
        print("Press Ctrl+C to stop")

        try:
            self.trade_engine.run_trading_loop(['EURUSD'])

        except KeyboardInterrupt:
            print("\nDemo mode stopped")

    def show_status(self):
        """Show system status"""
        print("SENTIENX System Status")
        print("=" * 30)

        # Show trade summary
        self.log_summary.display_trade_summary()

        # Show recent logs
        self.log_summary.display_recent_logs(5)

        # Show performance metrics
        self.log_summary.display_performance_metrics()

    def run_interactive_mode(self):
        """Run in interactive CLI mode"""
        print("SENTIENX Interactive Mode")
        print("Available commands:")
        print("  status     - Show system status")
        print("  train      - Run training cycle")
        print("  analyze    - Analyze market and show signals")
        print("  backtest   - Run backtest on historical data")
        print("  strategy   - Switch trading strategy")
        print("  logs       - Show recent logs")
        print("  exit       - Exit interactive mode")

        while True:
            try:
                cmd = input("\nSENTIENX> ").strip().lower()

                if cmd == 'status':
                    self.show_status()

                elif cmd == 'train':
                    print("Running training cycle...")
                    result = self.ml_pipeline.train_model('EURUSD')
                    if result:
                        print(f"Training completed with accuracy: {result['accuracy']:.4f}")
                    else:
                        print("Training failed")

                elif cmd == 'analyze':
                    print("Analyzing market...")
                    signal = self.trade_engine.analyze_market('EURUSD')
                    if signal:
                        print(f"Signal: {signal['action']} {signal['symbol']} "
                              f"with confidence {signal['confidence']:.2f}")
                    else:
                        print("No signal generated")

                elif cmd == 'backtest':
                    print("Running backtest...")
                    from datetime import datetime, timedelta
                    start_date = datetime.now() - timedelta(days=30)
                    end_date = datetime.now()

                    result = self.backtester.backtest_strategy('tls', 'EURUSD', start_date, end_date)
                    if result:
                        self.backtester.print_backtest_report(result, 'TLS Strategy')
                    else:
                        print("Backtest failed")

                elif cmd == 'strategy':
                    print("Available strategies: tls, ma_crossover, rsi_divergence")
                    strategy = input("Enter strategy name: ").strip()
                    if self.strategy_manager.set_active_strategy(strategy):
                        print(f"Strategy switched to: {strategy}")
                    else:
                        print("Invalid strategy name")

                elif cmd == 'logs':
                    self.log_summary.display_recent_logs(10)

                elif cmd == 'exit':
                    break

                else:
                    print("Unknown command. Type 'help' for available commands.")

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")

def main():
    parser = argparse.ArgumentParser(description='SENTIENX Trading System')
    parser.add_argument('mode', choices=['setup', 'train', 'trade', 'demo', 'interactive'],
                       help='Operation mode')
    parser.add_argument('--symbol', default='EURUSD', help='Trading symbol (default: EURUSD)')

    args = parser.parse_args()

    # Initialize SENTIENX
    sentienx = SENTIENX()

    if args.mode == 'setup':
        sentienx.setup_system()

    elif args.mode == 'train':
        sentienx.run_training_mode()

    elif args.mode == 'trade':
        confirm = input("WARNING: This will execute REAL trades. Continue? (yes/no): ")
        if confirm.lower() == 'yes':
            sentienx.run_trading_mode()
        else:
            print("Trading cancelled")

    elif args.mode == 'demo':
        sentienx.run_demo_mode()

    elif args.mode == 'interactive':
        sentienx.run_interactive_mode()

if __name__ == "__main__":
    main()