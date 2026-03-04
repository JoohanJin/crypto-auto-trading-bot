from src.brokers.base.ws_client import WebSocketClient
from src.interfaces.base.base_registry import BaseClientRegistry


class WebSocketClientRegistry(BaseClientRegistry[WebSocketClient]):
    def __init__(self, name: str | None) -> None:
        super().__init__(name=name if name else "WebSocketClientRegistry")

    def start(self) -> None:
        for key in self._registry:
            try:
                if hasattr(self._registry[key], "start"):
                    self._registry[key].start()
            except Exception as e:
                self.logger.warning(
                    f"[SERVICE_INIT_ERROR] {key} | Failed to start | Error: {type(e).__name__}: {e!s}"
                )
