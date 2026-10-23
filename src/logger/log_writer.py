import sqlite3
import logging
from datetime import datetime
from db_engine.database import DatabaseEngine

class Logger:
    def __init__(self, db_engine=None):
        self.db = db_engine or DatabaseEngine()
        self.setup_file_logging()

    def setup_file_logging(self):
        """Setup file logging for different modes"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('sentienx_training.log'),
                logging.FileHandler('sentienx_real.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('SENTIENX')

    def log_trade(self, trade_data):
        """Log trade information to database"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO trades (symbol, type, volume, entry_price, exit_price,
                              profit_loss, strategy, status, risk_percentage,
                              stop_loss, take_profit)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            trade_data.get('symbol'),
            trade_data.get('type'),
            trade_data.get('volume'),
            trade_data.get('entry_price'),
            trade_data.get('exit_price'),
            trade_data.get('profit_loss'),
            trade_data.get('strategy'),
            trade_data.get('status', 'OPEN'),
            trade_data.get('risk_percentage'),
            trade_data.get('stop_loss'),
            trade_data.get('take_profit')
        ))

        conn.commit()
        conn.close()

        self.logger.info(f"Trade logged: {trade_data}")

    def log_performance(self, metrics):
        """Log performance metrics"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO performance_metrics (date, total_trades, winning_trades,
                                          losing_trades, win_rate, total_profit,
                                          max_drawdown, sharpe_ratio)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().date(),
            metrics.get('total_trades'),
            metrics.get('winning_trades'),
            metrics.get('losing_trades'),
            metrics.get('win_rate'),
            metrics.get('total_profit'),
            metrics.get('max_drawdown'),
            metrics.get('sharpe_ratio')
        ))

        conn.commit()
        conn.close()

        self.logger.info(f"Performance metrics logged: {metrics}")

    def log_message(self, level, component, message):
        """Log general messages"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO logs (level, component, message)
            VALUES (?, ?, ?)
        ''', (level, component, message))

        conn.commit()
        conn.close()

        # Also log to file
        if level == 'ERROR':
            self.logger.error(f"{component}: {message}")
        elif level == 'WARNING':
            self.logger.warning(f"{component}: {message}")
        else:
            self.logger.info(f"{component}: {message}")

    def get_trade_summary(self):
        """Get summary of trades"""
        conn = self.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT COUNT(*) as total_trades,
                   SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) as winning_trades,
                   SUM(CASE WHEN profit_loss < 0 THEN 1 ELSE 0 END) as losing_trades,
                   AVG(profit_loss) as avg_profit,
                   SUM(profit_loss) as total_profit
            FROM trades
            WHERE status = 'CLOSED'
        ''')

        result = cursor.fetchone()
        conn.close()

        if result:
            total, winning, losing, avg_profit, total_profit = result
            win_rate = (winning / total * 100) if total > 0 else 0
            return {
                'total_trades': total,
                'winning_trades': winning,
                'losing_trades': losing,
                'win_rate': win_rate,
                'avg_profit': avg_profit,
                'total_profit': total_profit
            }
        return {}

if __name__ == "__main__":
    logger = Logger()
    logger.log_message('INFO', 'TEST', 'Logger initialized')