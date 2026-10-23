import sqlite3
import os

class DatabaseEngine:
    def __init__(self, db_path='sentienx.db'):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        """Initialize database with required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create trades table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                symbol TEXT NOT NULL,
                type TEXT NOT NULL,  -- BUY/SELL
                volume REAL NOT NULL,
                entry_price REAL NOT NULL,
                exit_price REAL,
                profit_loss REAL,
                strategy TEXT,
                status TEXT DEFAULT 'OPEN',  -- OPEN/CLOSED
                risk_percentage REAL,
                stop_loss REAL,
                take_profit REAL
            )
        ''')

        # Create market_data table for historical data
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS market_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME,
                symbol TEXT NOT NULL,
                open REAL,
                high REAL,
                low REAL,
                close REAL,
                volume REAL
            )
        ''')

        # Create performance_metrics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS performance_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE,
                total_trades INTEGER,
                winning_trades INTEGER,
                losing_trades INTEGER,
                win_rate REAL,
                total_profit REAL,
                max_drawdown REAL,
                sharpe_ratio REAL
            )
        ''')

        # Create logs table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                level TEXT,  -- INFO/ERROR/WARNING
                component TEXT,  -- trade_engine/logger/etc
                message TEXT
            )
        ''')

        conn.commit()
        conn.close()

    def get_connection(self):
        return sqlite3.connect(self.db_path)

if __name__ == "__main__":
    db = DatabaseEngine()
    print("Database initialized successfully")