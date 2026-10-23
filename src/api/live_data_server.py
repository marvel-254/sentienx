"""
WebSocket Server for Real-time Data Streaming
Live updates for dashboard metrics and trades
"""

import asyncio
import json
import threading
import time
from datetime import datetime
from pathlib import Path
import sqlite3
import pandas as pd
from typing import Dict, Set
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    import websockets
    from websockets.server import serve
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False
    logger.warning("websockets library not installed. Install with: pip install websockets")


class LiveDataServer:
    """WebSocket server for real-time data streaming"""
    
    def __init__(self, host="0.0.0.0", port=5001):
        self.host = host
        self.port = port
        self.clients: Set = set()
        self.db_path = Path(__file__).parent / "sentienx_trading.db"
        self.running = False
        
    async def handle_client(self, websocket, path):
        """Handle incoming WebSocket connections"""
        self.clients.add(websocket)
        logger.info(f"Client connected. Total clients: {len(self.clients)}")
        
        try:
            async for message in websocket:
                # Handle client requests
                data = json.loads(message)
                response = await self.process_request(data)
                await websocket.send(json.dumps(response))
        except websockets.exceptions.ConnectionClosed:
            logger.info("Client disconnected")
        finally:
            self.clients.discard(websocket)
    
    async def process_request(self, data: Dict) -> Dict:
        """Process incoming request and return response"""
        request_type = data.get('type', 'unknown')
        
        if request_type == 'subscribe_live':
            return {'status': 'subscribed', 'channel': data.get('channel')}
        elif request_type == 'get_account_data':
            return await self._get_account_data()
        elif request_type == 'get_trades':
            return await self._get_trades()
        elif request_type == 'get_bot_status':
            return await self._get_bot_status()
        elif request_type == 'get_gauge_data':
            return await self._get_gauge_data()
        elif request_type == 'get_pnl_data':
            return await self._get_pnl_data()
        else:
            return {'error': 'Unknown request type'}
    
    async def _get_account_data(self) -> Dict:
        """Get current account data"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT SUM(profit_loss) as total_profit, COUNT(*) as total_trades
                FROM trading_history WHERE status = 'closed'
            """)
            result = cursor.fetchone()
            conn.close()
            
            total_profit = result[0] or 0
            total_trades = result[1] or 0
            
            return {
                'type': 'account_data',
                'balance': 1000 + total_profit,
                'equity': 1000 + total_profit,
                'margin_used': 0,
                'margin_free': 1000 + total_profit,
                'total_trades': total_trades,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            return {'type': 'account_data', 'error': str(e)}
    
    async def _get_trades(self) -> Dict:
        """Get recent trades"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            query = """
                SELECT symbol, direction, entry_price, exit_price, profit_loss, timestamp
                FROM trading_history
                WHERE status = 'closed'
                ORDER BY timestamp DESC
                LIMIT 10
            """
            df = pd.read_sql_query(query, conn)
            conn.close()
            
            trades = []
            for _, row in df.iterrows():
                trades.append({
                    'symbol': row['symbol'],
                    'direction': row['direction'],
                    'entry': row['entry_price'],
                    'exit': row['exit_price'],
                    'pnl': row['profit_loss'],
                    'timestamp': row['timestamp']
                })
            
            return {
                'type': 'trades_data',
                'trades': trades,
                'count': len(trades),
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            return {'type': 'trades_data', 'error': str(e)}
    
    async def _get_bot_status(self) -> Dict:
        """Get bot status"""
        try:
            from process_manager import get_bot_status
            status = get_bot_status()
            return {
                'type': 'bot_status',
                'running': status['running'],
                'uptime': status.get('uptime', 0),
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            return {'type': 'bot_status', 'error': str(e)}
    
    async def _get_gauge_data(self) -> Dict:
        """Get bot strength gauge data"""
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent))
            from api_server import calculate_bot_strength
            
            strength = calculate_bot_strength()
            return {
                'type': 'gauge_data',
                'strength': strength,
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            return {'type': 'gauge_data', 'error': str(e)}
    
    async def _get_pnl_data(self) -> Dict:
        """Get P&L breakdown"""
        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent))
            from api_server import get_pnl_breakdown
            
            pnl = get_pnl_breakdown()
            return {
                'type': 'pnl_data',
                'profits': pnl['profitable_trades'],
                'losses': pnl['losing_trades'],
                'break_even': pnl['break_even'],
                'timestamp': datetime.now().isoformat()
            }
        except Exception as e:
            return {'type': 'pnl_data', 'error': str(e)}
    
    async def broadcast_update(self, data: Dict):
        """Broadcast update to all connected clients"""
        if self.clients:
            message = json.dumps(data)
            disconnected = set()
            for client in self.clients:
                try:
                    await asyncio.wait_for(client.send(message), timeout=5)
                except Exception as e:
                    logger.error(f"Error sending to client: {e}")
                    disconnected.add(client)
            
            for client in disconnected:
                self.clients.discard(client)
    
    async def start(self):
        """Start WebSocket server"""
        self.running = True
        logger.info(f"WebSocket server starting on ws://{self.host}:{self.port}")
        async with serve(self.handle_client, self.host, self.port):
            logger.info(f"WebSocket server running on ws://{self.host}:{self.port}")
            await asyncio.Future()  # Run forever
    
    def run_in_thread(self):
        """Run server in background thread"""
        def run_async():
            asyncio.run(self.start())
        
        thread = threading.Thread(target=run_async, daemon=True)
        thread.start()
        time.sleep(1)  # Give server time to start
        logger.info("WebSocket server started in background thread")


def get_live_server(host="0.0.0.0", port=5001):
    """Get or create live data server instance"""
    if not HAS_WEBSOCKETS:
        logger.error("websockets library required. Install with: pip install websockets")
        return None
    return LiveDataServer(host, port)


if __name__ == "__main__":
    if HAS_WEBSOCKETS:
        server = LiveDataServer()
        try:
            asyncio.run(server.start())
        except KeyboardInterrupt:
            print("Server stopped")
    else:
        print("Please install websockets: pip install websockets")
