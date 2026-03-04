# Backward compatibility re-exports
# Import from the new split files instead
from src.brokers.base.ws_service import WebSocket
from src.brokers.base.ws_client import WebSocketClient

__all__ = ["WebSocket", "WebSocketClient"]
