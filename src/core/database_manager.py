"""
SENTIENX Database Manager v2.0
Enhanced database functionality with advanced analytics, performance tracking, and signal history
"""

import pandas as pd
from datetime import datetime, timedelta
import sqlite3
from typing import Dict, List, Optional, Tuple, Any
import json
import numpy as np
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)

class DatabaseManager:
    """Manages all database operations for SENTIENX"""

    def __init__(self, db_path: str = 'sentienx_memory.db'):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """Initialize SQLite database with all required tables - v2.0 with enhanced schema"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create all tables with enhanced schema
        cursor.executescript('''
            -- Training data table (Enhanced)
            CREATE TABLE IF NOT EXISTS training_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                symbol VARCHAR(10) NOT NULL,
                timeframe VARCHAR(5) NOT NULL,
                rsi REAL, macd REAL, macd_signal REAL, macd_histogram REAL,
                bb_upper REAL, bb_lower REAL, bb_middle REAL, bb_position REAL,
                sma_5 REAL, sma_10 REAL, sma_20 REAL,
                ema_5 REAL, ema_10 REAL,
                atr REAL, momentum_5 REAL, momentum_10 REAL,
                volume_ratio REAL,
                price_change REAL, direction INTEGER, confidence REAL,
                data_source VARCHAR(50), quality_score REAL, notes TEXT,
                INDEX idx_symbol_time (symbol, timestamp)
            );

            -- Predictions table (Enhanced)
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                symbol VARCHAR(10) NOT NULL,
                model_version VARCHAR(50),
                input_features TEXT,
                raw_prediction REAL, signal VARCHAR(10), confidence REAL,
                ensemble_used BOOLEAN DEFAULT 0, mtf_alignment REAL DEFAULT 0.0,
                actual_direction INTEGER, actual_change REAL, outcome VARCHAR(20),
                position_size REAL, entry_price REAL, exit_price REAL, profit_loss REAL,
                trade_duration INTEGER, model_accuracy REAL, prediction_quality REAL,
                is_confirmed BOOLEAN DEFAULT 0, confirmation_factors INTEGER DEFAULT 0,
                signal_strength VARCHAR(20),
                INDEX idx_symbol_time (symbol, timestamp),
                INDEX idx_outcome (outcome)
            );

            -- Model versions table (Enhanced)
            CREATE TABLE IF NOT EXISTS model_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version_name VARCHAR(100) UNIQUE,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                input_size INTEGER, hidden_sizes TEXT, output_size INTEGER,
                learning_rate REAL, training_samples INTEGER, epochs_trained INTEGER,
                final_accuracy REAL, validation_accuracy REAL,
                precision REAL, recall REAL, f1_score REAL,
                total_predictions INTEGER, correct_predictions INTEGER,
                win_rate REAL, profit_factor REAL, max_drawdown REAL,
                sharpe_ratio REAL, avg_confidence REAL,
                model_file_path VARCHAR(255), training_log TEXT,
                model_insights TEXT,
                is_active BOOLEAN DEFAULT 0, deployed_at DATETIME,
                INDEX idx_active (is_active)
            );

            -- Market data cache (Enhanced)
            CREATE TABLE IF NOT EXISTS market_data_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol VARCHAR(10) NOT NULL,
                timestamp DATETIME NOT NULL,
                timeframe VARCHAR(5) NOT NULL,
                open REAL NOT NULL, high REAL NOT NULL, low REAL NOT NULL,
                close REAL NOT NULL, volume INTEGER,
                spread REAL, bid REAL, ask REAL,
                volatility REAL, trend_direction VARCHAR(10),
                data_source VARCHAR(50),
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(symbol, timestamp, timeframe),
                INDEX idx_symbol_time (symbol, timestamp)
            );

            -- System performance (Enhanced)
            CREATE TABLE IF NOT EXISTS system_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                cpu_usage REAL, memory_usage REAL, disk_usage REAL,
                active_model_version VARCHAR(100),
                predictions_per_minute REAL, average_confidence REAL,
                active_positions INTEGER, total_equity REAL, daily_pnl REAL,
                win_rate_today REAL, data_points_processed INTEGER,
                api_calls_made INTEGER, cache_hit_rate REAL,
                database_size_mb REAL,
                response_time_ms REAL,
                INDEX idx_timestamp (timestamp)
            );

            -- Signal history (NEW)
            CREATE TABLE IF NOT EXISTS signal_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                symbol VARCHAR(10) NOT NULL,
                signal_type VARCHAR(20) NOT NULL,
                signal VARCHAR(10),
                confidence REAL,
                timeframe VARCHAR(5),
                source VARCHAR(50),
                anomalies_detected TEXT,
                mtf_consensus REAL DEFAULT 0.0,
                is_false_signal BOOLEAN DEFAULT 0,
                notes TEXT,
                INDEX idx_symbol_signal (symbol, timestamp, signal)
            );

            -- Trading statistics (NEW)
            CREATE TABLE IF NOT EXISTS trading_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE UNIQUE NOT NULL,
                symbol VARCHAR(10),
                total_trades INTEGER DEFAULT 0,
                winning_trades INTEGER DEFAULT 0,
                losing_trades INTEGER DEFAULT 0,
                win_rate REAL DEFAULT 0.0,
                total_pnl REAL DEFAULT 0.0,
                avg_profit REAL DEFAULT 0.0,
                avg_loss REAL DEFAULT 0.0,
                profit_factor REAL DEFAULT 0.0,
                max_drawdown REAL DEFAULT 0.0,
                sharpe_ratio REAL DEFAULT 0.0,
                largest_win REAL DEFAULT 0.0,
                largest_loss REAL DEFAULT 0.0,
                consecutive_wins INTEGER DEFAULT 0,
                consecutive_losses INTEGER DEFAULT 0,
                INDEX idx_date (date)
            );

            -- Feature importance tracking (NEW)
            CREATE TABLE IF NOT EXISTS feature_importance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_version VARCHAR(100) NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                feature_name VARCHAR(100),
                importance_score REAL,
                rank INTEGER,
                INDEX idx_model_feature (model_version, feature_name)
            );

            -- Anomaly log (NEW)
            CREATE TABLE IF NOT EXISTS anomaly_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                symbol VARCHAR(10) NOT NULL,
                anomaly_type VARCHAR(50),
                severity REAL,
                price REAL,
                details TEXT,
                action_taken VARCHAR(100),
                INDEX idx_symbol_time (symbol, timestamp)
            );

            -- System health metrics (NEW)
            CREATE TABLE IF NOT EXISTS system_health (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                health_status VARCHAR(20),
                uptime_seconds INTEGER,
                models_trained INTEGER,
                total_predictions INTEGER,
                average_latency_ms REAL,
                error_count INTEGER,
                last_error TEXT,
                INDEX idx_timestamp (timestamp)
            );
        ''')

        # Create indices for frequently queried columns
        try:
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_pred_symbol ON predictions(symbol)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_pred_outcome ON predictions(outcome)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_market_symbol ON market_data_cache(symbol)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_signal_symbol ON signal_history(symbol)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_stats_date ON trading_stats(date)')
        except:
            pass

        conn.commit()
        conn.close()
        logger.info("✅ Database v2.0 initialized with all tables and indices")

    def store_market_data(self, symbol: str, timeframe: str, candle: Dict):
        """Store market data in cache"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    INSERT OR REPLACE INTO market_data_cache
                    (symbol, timestamp, timeframe, open, high, low, close, volume, spread, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    symbol,
                    candle['time'] if isinstance(candle, dict) and 'time' in candle else datetime.now().isoformat(),
                    timeframe,
                    float(candle.get('open', candle.get('o', 1.0850))),
                    float(candle.get('high', candle.get('h', 1.0852))),
                    float(candle.get('low', candle.get('l', 1.0848))),
                    float(candle.get('close', candle.get('c', 1.0850))),
                    candle.get('volume', 1000),
                    candle.get('spread', 2),
                    datetime.now().isoformat()
                ))

                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Database error storing market data: {str(e)}")

    def get_recent_data(self, symbol: str, timeframe: str, limit: int = 100) -> pd.DataFrame:
        """Get recent market data for model input"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                df = pd.read_sql_query('''
                    SELECT * FROM market_data_cache
                    WHERE symbol = ? AND timeframe = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                ''', conn, params=(symbol, timeframe, limit))

                return df.sort_values('timestamp') if not df.empty else pd.DataFrame()
        except sqlite3.Error as e:
            logger.error(f"Database error getting recent data: {str(e)}")
            return pd.DataFrame()

    def store_prediction(self, prediction_data: Dict):
        """Store model prediction in database"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                cursor.execute('''
                    INSERT INTO predictions
                    (symbol, model_version, input_features, raw_prediction, signal, confidence,
                     position_size, entry_price)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    prediction_data['symbol'],
                    prediction_data.get('model_version', 'v1.0'),
                    json.dumps(prediction_data.get('input_features', {})),
                    prediction_data['raw_prediction'],
                    prediction_data['signal'],
                    prediction_data['confidence'],
                    prediction_data.get('position_size', 0.01),
                    prediction_data.get('entry_price', 0)
                ))

                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Database error storing prediction: {str(e)}")

    def update_prediction_outcome(self, prediction_id: int, outcome: Dict):
        """Update prediction with actual results"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            UPDATE predictions
            SET actual_direction = ?, actual_change = ?, outcome = ?,
                exit_price = ?, profit_loss = ?, trade_duration = ?
            WHERE id = ?
        ''', (
            outcome['actual_direction'],
            outcome['actual_change'],
            outcome['outcome'],
            outcome.get('exit_price'),
            outcome.get('profit_loss'),
            outcome.get('trade_duration'),
            prediction_id
        ))

        conn.commit()
        conn.close()

    def load_training_data(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Load training data from database"""
        conn = sqlite3.connect(self.db_path)

        # Get recent training data (last 1000 samples)
        df = pd.read_sql_query('''
            SELECT * FROM training_data
            ORDER BY timestamp DESC
            LIMIT 1000
        ''', conn)

        conn.close()

        if df.empty:
            # Return empty arrays if no data
            return np.array([]), np.array([]), np.array([]), np.array([])

        # Prepare features and targets
        # This is simplified - in production you'd use data_processor.py
        feature_cols = ['rsi', 'macd', 'bb_position', 'momentum_5']
        X = df[feature_cols].fillna(0).values
        y = df['direction'].fillna(0).values

        # Split into train/validation
        split_idx = int(len(X) * 0.8)
        X_train, X_test = X[:split_idx], X[split_idx:]
        y_train, y_test = y[:split_idx], y[split_idx:]

        return X_train, X_test, y_train, y_test

    def save_model_version(self, version_data: Dict):
        """Save model version information"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO model_versions
            (version_name, input_size, hidden_sizes, output_size, learning_rate,
             training_samples, epochs_trained, final_accuracy, validation_accuracy,
             model_file_path, is_active, deployed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            version_data['version_name'],
            version_data.get('input_size', 17),
            json.dumps(version_data.get('hidden_sizes', [64, 32, 16])),
            version_data.get('output_size', 1),
            version_data.get('learning_rate', 0.001),
            version_data.get('training_samples', 1000),
            version_data.get('epochs_trained', 500),
            version_data.get('final_accuracy', 0.85),
            version_data.get('validation_accuracy', 0.82),
            version_data.get('model_file_path', ''),
            version_data.get('is_active', 1),
            datetime.now().isoformat()
        ))

        conn.commit()
        conn.close()

    def get_prediction_stats(self) -> Dict:
        """Get prediction statistics"""
        conn = sqlite3.connect(self.db_path)

        cursor = conn.cursor()
        cursor.execute('''
            SELECT
                COUNT(*) as total_predictions,
                AVG(confidence) as avg_confidence,
                SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN outcome = 'LOSS' THEN 1 ELSE 0 END) as losses
            FROM predictions
            WHERE outcome IN ('WIN', 'LOSS')
        ''')

        result = cursor.fetchone()
        conn.close()

        if result:
            total, avg_conf, wins, losses = result
            wins = wins or 0
            losses = losses or 0
            win_rate = (wins / (wins + losses)) * 100 if (wins + losses) > 0 else 0

            return {
                'total_predictions': total,
                'average_confidence': avg_conf or 0,
                'wins': wins,
                'losses': losses,
                'win_rate': win_rate
            }

        return {'total_predictions': 0, 'average_confidence': 0, 'wins': 0, 'losses': 0, 'win_rate': 0}

    def get_system_performance(self) -> Dict:
        """Get latest system performance metrics"""
        conn = sqlite3.connect(self.db_path)

        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM system_performance
            ORDER BY timestamp DESC
            LIMIT 1
        ''')

        result = cursor.fetchone()
        conn.close()

        if result:
            return {
                'cpu_usage': result[2],
                'memory_usage': result[3],
                'disk_usage': result[4],
                'predictions_per_minute': result[6] or 0,
                'average_confidence': result[7] or 0,
                'timestamp': result[1]
            }

        return {
            'cpu_usage': 0,
            'memory_usage': 0,
            'disk_usage': 0,
            'predictions_per_minute': 0,
            'average_confidence': 0,
            'timestamp': datetime.now().isoformat()
        }

    def generate_sample_data(self, symbol: str = 'EURUSD', days: int = 30):
        """Generate sample market data for testing"""
        logger.info(f"Generating {days} days of sample data for {symbol}...")

        # Generate timestamps
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        timestamps = pd.date_range(start_date, end_date, freq='1H')

        # Generate realistic price movements
        base_price = 1.0850 if symbol == 'EURUSD' else 1.2750
        prices = [base_price]

        np.random.seed(42)  # For reproducible results

        for i in range(len(timestamps) - 1):
            # Add trend + random walk + volatility
            trend = 0.00001 * np.sin(i / 100)  # Slight cyclical trend
            change = np.random.normal(0, 0.0008)  # Hourly volatility
            new_price = prices[-1] + change + trend
            prices.append(max(new_price, base_price * 0.95))  # Floor price

        # Create OHLCV data
        candles = []
        for i, (ts, price) in enumerate(zip(timestamps, prices)):
            # Generate OHLC from close price
            volatility = abs(np.random.normal(0, 0.0005))
            high = price + volatility
            low = price - volatility
            open_price = price + np.random.normal(0, volatility/3)
            volume = np.random.randint(1000, 10000)

            candle = {
                'time': ts.isoformat(),
                'open': round(open_price, 5),
                'high': round(high, 5),
                'low': round(low, 5),
                'close': round(price, 5),
                'volume': volume,
                'spread': 2
            }

            candles.append(candle)
            self.store_market_data(symbol, 'H1', candle)

        logger.info(f"✅ Generated {len(candles)} candles for {symbol}")
        return candles

    # ============= NEW ANALYTICS METHODS =============

    def record_signal(self, symbol: str, signal_type: str, signal: str, confidence: float,
                     timeframe: str, source: str, anomalies: List[str] = None, mtf_consensus: float = 0.0):
        """Record signal generation in history"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO signal_history
            (symbol, signal_type, signal, confidence, timeframe, source, anomalies_detected, mtf_consensus)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            symbol, signal_type, signal, confidence, timeframe, source,
            json.dumps(anomalies or []), mtf_consensus
        ))

        conn.commit()
        conn.close()

    def record_anomaly(self, symbol: str, anomaly_type: str, severity: float,
                      price: float, details: str = "", action: str = ""):
        """Record detected anomaly"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO anomaly_log
            (symbol, anomaly_type, severity, price, details, action_taken)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (symbol, anomaly_type, severity, price, details, action))

        conn.commit()
        conn.close()

    def update_trading_stats(self, date: str, symbol: str, stats: Dict):
        """Update daily trading statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT OR REPLACE INTO trading_stats
            (date, symbol, total_trades, winning_trades, losing_trades, win_rate,
             total_pnl, avg_profit, avg_loss, profit_factor, max_drawdown, sharpe_ratio,
             largest_win, largest_loss, consecutive_wins, consecutive_losses)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            date, symbol,
            stats.get('total_trades', 0),
            stats.get('winning_trades', 0),
            stats.get('losing_trades', 0),
            stats.get('win_rate', 0.0),
            stats.get('total_pnl', 0.0),
            stats.get('avg_profit', 0.0),
            stats.get('avg_loss', 0.0),
            stats.get('profit_factor', 0.0),
            stats.get('max_drawdown', 0.0),
            stats.get('sharpe_ratio', 0.0),
            stats.get('largest_win', 0.0),
            stats.get('largest_loss', 0.0),
            stats.get('consecutive_wins', 0),
            stats.get('consecutive_losses', 0)
        ))

        conn.commit()
        conn.close()

    def get_dashboard_summary(self) -> Dict:
        """Get comprehensive dashboard summary"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get recent performance
        cursor.execute('''
            SELECT COUNT(*) as total, 
                   SUM(CASE WHEN outcome = 'WIN' THEN 1 ELSE 0 END) as wins,
                   SUM(CASE WHEN outcome = 'LOSS' THEN 1 ELSE 0 END) as losses,
                   AVG(confidence) as avg_conf,
                   AVG(profit_loss) as avg_pnl
            FROM predictions WHERE timestamp > datetime('now', '-24 hours')
        ''')
        perf = cursor.fetchone()

        # Get today's stats
        cursor.execute('''
            SELECT * FROM trading_stats WHERE date = DATE('now') LIMIT 1
        ''')
        today = cursor.fetchone()

        # Get system health
        cursor.execute('''
            SELECT health_status, uptime_seconds, models_trained, average_latency_ms
            FROM system_health ORDER BY timestamp DESC LIMIT 1
        ''')
        health = cursor.fetchone()

        # Get active model
        cursor.execute('''
            SELECT version_name, accuracy, win_rate FROM model_versions
            WHERE is_active = 1 LIMIT 1
        ''')
        model = cursor.fetchone()

        conn.close()

        return {
            'performance': {
                'total_predictions': perf[0] if perf else 0,
                'wins': perf[1] if perf else 0,
                'losses': perf[2] if perf else 0,
                'win_rate': (perf[1] / perf[0] * 100) if perf and perf[0] > 0 else 0,
                'avg_confidence': perf[3] if perf else 0,
                'avg_pnl': perf[4] if perf else 0
            },
            'today_stats': {
                'total_trades': today[2] if today else 0,
                'total_pnl': today[6] if today else 0,
                'win_rate': today[4] if today else 0,
                'profit_factor': today[9] if today else 0
            } if today else {},
            'system_health': {
                'status': health[0] if health else 'UNKNOWN',
                'uptime_hours': (health[1] / 3600) if health else 0,
                'models_trained': health[2] if health else 0,
                'avg_latency_ms': health[3] if health else 0
            } if health else {},
            'active_model': {
                'name': model[0] if model else 'None',
                'accuracy': model[1] if model else 0,
                'win_rate': model[2] if model else 0
            } if model else {}
        }

    def get_performance_history(self, days: int = 30, symbol: str = None) -> List[Dict]:
        """Get historical performance data for charting"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = '''
            SELECT date, total_trades, win_rate, total_pnl, profit_factor, sharpe_ratio
            FROM trading_stats
            WHERE date >= DATE('now', '-' || ? || ' days')
        '''
        params = [days]

        if symbol:
            query += ' AND symbol = ?'
            params.append(symbol)

        query += ' ORDER BY date ASC'

        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()

        return [
            {
                'date': r[0],
                'trades': r[1],
                'win_rate': r[2],
                'pnl': r[3],
                'profit_factor': r[4],
                'sharpe_ratio': r[5]
            }
            for r in results
        ]

    def get_signal_analysis(self, symbol: str = None, limit: int = 100) -> List[Dict]:
        """Get signal history analysis"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = '''
            SELECT timestamp, symbol, signal_type, signal, confidence, mtf_consensus,
                   is_false_signal, anomalies_detected
            FROM signal_history
        '''
        params = []

        if symbol:
            query += ' WHERE symbol = ?'
            params.append(symbol)

        query += ' ORDER BY timestamp DESC LIMIT ?'
        params.append(limit)

        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()

        return [
            {
                'timestamp': r[0],
                'symbol': r[1],
                'type': r[2],
                'signal': r[3],
                'confidence': r[4],
                'mtf_consensus': r[5],
                'is_false': r[6],
                'anomalies': json.loads(r[7]) if r[7] else []
            }
            for r in results
        ]

    def get_model_comparison(self) -> List[Dict]:
        """Compare all model versions"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT version_name, created_at, final_accuracy, precision, recall, f1_score,
                   win_rate, profit_factor, total_predictions, is_active
            FROM model_versions ORDER BY created_at DESC
        ''')

        results = cursor.fetchall()
        conn.close()

        return [
            {
                'name': r[0],
                'created': r[1],
                'accuracy': r[2],
                'precision': r[3],
                'recall': r[4],
                'f1_score': r[5],
                'win_rate': r[6],
                'profit_factor': r[7],
                'predictions': r[8],
                'is_active': bool(r[9])
            }
            for r in results
        ]

    def get_feature_importance_ranking(self, model_version: str, limit: int = 10) -> List[Dict]:
        """Get top N features by importance for a model"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT feature_name, importance_score, rank
            FROM feature_importance
            WHERE model_version = ? AND rank <= ?
            ORDER BY rank ASC
        ''', (model_version, limit))

        results = cursor.fetchall()
        conn.close()

        return [
            {
                'feature': r[0],
                'importance': r[1],
                'rank': r[2]
            }
            for r in results
        ]

    def get_system_metrics(self, hours: int = 24) -> Dict:
        """Get system performance metrics over time"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT timestamp, cpu_usage, memory_usage, predictions_per_minute,
                   average_confidence, cache_hit_rate, response_time_ms
            FROM system_performance
            WHERE timestamp > datetime('now', '-' || ? || ' hours')
            ORDER BY timestamp ASC
        ''', (hours,))

        results = cursor.fetchall()
        conn.close()

        return {
            'timestamps': [r[0] for r in results],
            'cpu': [r[1] for r in results],
            'memory': [r[2] for r in results],
            'predictions_pm': [r[3] for r in results],
            'confidence': [r[4] for r in results],
            'cache_hit': [r[5] for r in results],
            'response_time': [r[6] for r in results]
        }

    def export_analytics_report(self, filename: str = 'analytics_report.json') -> str:
        """Export comprehensive analytics report"""
        report = {
            'generated_at': datetime.now().isoformat(),
            'summary': self.get_dashboard_summary(),
            'performance_history': self.get_performance_history(30),
            'signal_analysis': self.get_signal_analysis(limit=50),
            'model_comparison': self.get_model_comparison(),
            'system_metrics': self.get_system_metrics(24)
        }

        with open(filename, 'w') as f:
            json.dump(report, f, indent=2, default=str)

        logger.info(f"✅ Analytics report exported to {filename}")
        return filename

# Test the database manager
if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)

    db = DatabaseManager()
    db.generate_sample_data('EURUSD', 7)

    # Test new methods
    db.record_signal('EURUSD', 'TREND', 'BUY', 0.82, '1H', 'ensemble', ['rsi_extreme'], 0.85)
    db.record_anomaly('EURUSD', 'price_spike', 0.92, 1.0850, 'Z-score > 3', 'reduced_position')

    stats = db.get_prediction_stats()
    print(f"📊 Prediction stats: {stats}")

    summary = db.get_dashboard_summary()
    print(f"📈 Dashboard summary: {json.dumps(summary, indent=2, default=str)}")

    signals = db.get_signal_analysis('EURUSD', 10)
    print(f"📡 Recent signals: {len(signals)} found")

    models = db.get_model_comparison()
    print(f"🤖 Model comparison: {len(models)} models")

    perf_history = db.get_performance_history(30)
    print(f"📉 Performance history: {len(perf_history)} days")

    sys_metrics = db.get_system_metrics(24)
    print(f"⚙️ System metrics: {len(sys_metrics.get('timestamps', []))} data points")