"""
WebSocket Client Helper for Dashboard Live Data
"""

import asyncio
import json
import threading
from typing import Dict, Callable, Optional
import logging

logger = logging.getLogger(__name__)

try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False


class WebSocketClient:
    """Client for connecting to live data WebSocket server"""
    
    def __init__(self, uri="ws://localhost:5001", auto_connect=False):
        self.uri = uri
        self.connected = False
        self.websocket = None
        self.callbacks: Dict[str, list] = {}
        
        if auto_connect and HAS_WEBSOCKETS:
            self.connect_async()
    
    def connect_async(self):
        """Connect in background thread"""
        thread = threading.Thread(target=self._async_connect, daemon=True)
        thread.start()
    
    def _async_connect(self):
        """Async connection runner"""
        try:
            asyncio.run(self._connect())
        except Exception as e:
            logger.warning(f"WebSocket connection failed: {e}")
    
    async def _connect(self):
        """Connect to WebSocket server"""
        try:
            async with websockets.connect(self.uri) as websocket:
                self.websocket = websocket
                self.connected = True
                logger.info("WebSocket connected")
                
                while self.connected:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=30)
                        data = json.loads(message)
                        self._trigger_callbacks(data.get('type', 'unknown'), data)
                    except asyncio.TimeoutError:
                        pass
                    except Exception as e:
                        logger.error(f"Error receiving message: {e}")
                        break
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            self.connected = False
    
    def send(self, request: Dict):
        """Send request to WebSocket server (non-blocking)"""
        if self.connected and self.websocket:
            try:
                asyncio.run(self.websocket.send(json.dumps(request)))
            except Exception as e:
                logger.error(f"Error sending message: {e}")
    
    def request(self, request_type: str, **kwargs) -> Dict:
        """Make a request to WebSocket server"""
        request = {'type': request_type}
        request.update(kwargs)
        self.send(request)
        return request
    
    def on(self, message_type: str, callback: Callable):
        """Register callback for message type"""
        if message_type not in self.callbacks:
            self.callbacks[message_type] = []
        self.callbacks[message_type].append(callback)
    
    def _trigger_callbacks(self, message_type: str, data: Dict):
        """Trigger registered callbacks"""
        if message_type in self.callbacks:
            for callback in self.callbacks[message_type]:
                try:
                    callback(data)
                except Exception as e:
                    logger.error(f"Error in callback: {e}")
    
    def disconnect(self):
        """Disconnect from WebSocket"""
        self.connected = False
        if self.websocket:
            asyncio.run(self.websocket.close())


# Global client instance
_client: Optional[WebSocketClient] = None


def get_websocket_client() -> Optional[WebSocketClient]:
    """Get or create global WebSocket client"""
    global _client
    if _client is None and HAS_WEBSOCKETS:
        _client = WebSocketClient(auto_connect=True)
    return _client


def ws_request(request_type: str, **kwargs) -> Dict:
    """Make WebSocket request"""
    client = get_websocket_client()
    if client:
        return client.request(request_type, **kwargs)
    return {}
