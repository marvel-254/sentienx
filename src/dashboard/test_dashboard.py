#!/usr/bin/env python3
"""
Test script to verify dashboard functionality without Streamlit UI
"""

import sys
import sqlite3
import os
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Test configuration
BASE_DIR = Path(__file__).parent.parent
DB_PATH = BASE_DIR / "sentienx_trading.db"

def initialize_db():
    """Initialize database"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='trading_history'
        """)
        
        if not cursor.fetchone():
            cursor.execute('''
                CREATE TABLE trading_history (
                    id INTEGER PRIMARY KEY,
                    symbol TEXT,
                    direction TEXT,
                    entry_price REAL,
                    exit_price REAL,
                    volume REAL,
                    profit_loss REAL,
                    status TEXT,
                    timestamp TEXT,
                    strategy TEXT
                )
            ''')
            conn.commit()
        
        conn.close()
    except Exception as e:
        print(f"DB init error: {e}")

def test_database_connection():
    """Test database connection"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        conn.close()
        print("✓ Database connection successful")
        return True
    except Exception as e:
        print(f"✗ Database error: {e}")
        return False

def test_database_permissions():
    """Test database file permissions"""
    try:
        if DB_PATH.exists():
            stat_info = os.stat(str(DB_PATH))
            mode = stat_info.st_mode
            print(f"✓ Database permissions: {oct(mode)}")
            return True
        else:
            print("✗ Database file not found")
            return False
    except Exception as e:
        print(f"✗ Permission test error: {e}")
        return False

def test_sample_data_insertion():
    """Test inserting and retrieving sample data"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Insert sample trade
        cursor.execute('''
            INSERT INTO trading_history 
            (symbol, direction, entry_price, exit_price, volume, profit_loss, status, timestamp, strategy)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', ('EURUSD', 'BUY', 1.0850, 1.0870, 1.0, 20.0, 'closed', datetime.now().isoformat(), 'test_strategy'))
        
        conn.commit()
        
        # Verify insertion
        cursor.execute("SELECT COUNT(*) as count FROM trading_history")
        result = cursor.fetchone()
        count = result['count']
        
        conn.close()
        
        if count > 0:
            print(f"✓ Sample data insertion successful (total records: {count})")
            return True
        else:
            print("✗ Failed to insert sample data")
            return False
    except Exception as e:
        print(f"✗ Data insertion error: {e}")
        return False

def test_account_data_loading():
    """Test account data structure"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN profit_loss > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN profit_loss < 0 THEN 1 ELSE 0 END) as losses,
                SUM(profit_loss) as total_pnl
            FROM trading_history
        ''')
        
        stats = cursor.fetchone()
        conn.close()
        
        account = {
            'balance': 1000.0,
            'equity': 1050.0,
            'total_trades': stats['total'] or 0,
            'winning_trades': stats['wins'] or 0,
            'losing_trades': stats['losses'] or 0,
            'total_pnl': stats['total_pnl'] or 0.0
        }
        
        print(f"✓ Account data loaded: {account['total_trades']} trades, P&L: ${account['total_pnl']:.2f}")
        return True
    except Exception as e:
        print(f"✗ Account data error: {e}")
        return False

def test_pnl_data_loading():
    """Test P&L data loading"""
    try:
        conn = sqlite3.connect(str(DB_PATH))
        
        query = '''
            SELECT 
                DATE(timestamp) as date,
                SUM(profit_loss) as daily_pnl,
                COUNT(*) as trades
            FROM trading_history 
            GROUP BY DATE(timestamp)
            ORDER BY date ASC
        '''
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
            df['cumulative_pnl'] = df['daily_pnl'].cumsum()
            print(f"✓ P&L data loaded: {len(df)} days of data")
        else:
            print("✓ P&L data loaded: No data yet (empty is OK)")
        
        return True
    except Exception as e:
        print(f"✗ P&L data error: {e}")
        return False

def main():
    """Run all tests"""
    print("\n=== DASHBOARD FUNCTIONALITY TESTS ===\n")
    
    # Initialize database first
    initialize_db()
    
    tests = [
        ("Database Connection", test_database_connection),
        ("Database Permissions", test_database_permissions),
        ("Sample Data Insertion", test_sample_data_insertion),
        ("Account Data Loading", test_account_data_loading),
        ("P&L Data Loading", test_pnl_data_loading),
    ]
    
    results = []
    for name, test_func in tests:
        print(f"\nTesting: {name}")
        try:
            result = test_func()
            results.append(result)
        except Exception as e:
            print(f"✗ Unexpected error: {e}")
            results.append(False)
    
    passed = sum(results)
    total = len(results)
    
    print(f"\n=== RESULTS ===")
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("All tests passed! Dashboard is ready to use.")
        return 0
    else:
        print(f"Some tests failed. Check the errors above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
