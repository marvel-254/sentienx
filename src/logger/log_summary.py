from logger.log_writer import Logger

class LogSummary:
    def __init__(self, logger=None):
        self.logger = logger or Logger()

    def display_trade_summary(self):
        """Display trade summary on CLI"""
        summary = self.logger.get_trade_summary()

        print("\n=== TRADE SUMMARY ===")
        print(f"Total Trades: {summary.get('total_trades', 0)}")
        print(f"Winning Trades: {summary.get('winning_trades', 0)}")
        print(f"Losing Trades: {summary.get('losing_trades', 0)}")
        print(".2f")
        print(".2f")
        print(".2f")
        print("=" * 20)

    def display_recent_logs(self, limit=10):
        """Display recent logs"""
        conn = self.logger.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT timestamp, level, component, message
            FROM logs
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (limit,))

        logs = cursor.fetchall()
        conn.close()

        print("\n=== RECENT LOGS ===")
        for log in logs:
            timestamp, level, component, message = log
            print(f"[{timestamp}] {level} - {component}: {message}")
        print("=" * 20)

    def display_performance_metrics(self):
        """Display latest performance metrics"""
        conn = self.logger.db.get_connection()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT * FROM performance_metrics
            ORDER BY date DESC
            LIMIT 1
        ''')

        result = cursor.fetchone()
        conn.close()

        if result:
            print("\n=== PERFORMANCE METRICS ===")
            print(f"Date: {result[1]}")
            print(f"Total Trades: {result[2]}")
            print(f"Winning Trades: {result[3]}")
            print(f"Losing Trades: {result[4]}")
            print(".2f")
            print(".2f")
            print(".2f")
            print(".2f")
            print("=" * 25)

if __name__ == "__main__":
    summary = LogSummary()
    summary.display_trade_summary()
    summary.display_recent_logs()
    summary.display_performance_metrics()