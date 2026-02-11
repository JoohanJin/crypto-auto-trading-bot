# Standard Library
from collections.abc import Callable

# Custom Library
from src.brokers.base.ws_sdk import WebSocketClient
from src.core.models.trade import TradePair
from src.interfaces.base.base_registry import BaseClientRegistry
from src.interfaces.base.base_interface import BaseInterface
from src.infrastructure.logging.set_logger import get_logger

logger = get_logger(__name__)


class WebSocketClientRegistry(BaseClientRegistry[WebSocketClient]):
    def __init__(self, name: str | None) -> None:
        super().__init__(name=name if name else "WebSocketClientRegistry")

    def start(self) -> None:
        for key in self._registry:
            try:
                if hasattr(self._registry[key], 'start'):
                    self._registry[key].start()
            except Exception as e:
                self.logger.warning(f"{str(e)}")
        return


class WebSocketInterface(BaseInterface[WebSocketClientRegistry, WebSocketClient]):
    def __init__(
        self,
        client_registry: WebSocketClientRegistry | None = None,
        trade_pair: TradePair | None = None,
        name: str | None = None,
    ) -> None:
        self.trade_pair = TradePair("BTC", "USDT") if trade_pair is None else trade_pair
        
        registry = (
            client_registry
            if client_registry
            else WebSocketClientRegistry(name="DEFAULT_WEBSOCKET_CLIENT_REGISTRY")
        )
        
        super().__init__(
            client_registry=registry,
            name=name if name else "WebSocketInterface"
        )

    def push_client(
        self,
        key: str,
        client: WebSocketClient,
    ) -> None:
        if isinstance(client, WebSocketClient):
            super().push_client(key, client)
        else:
            # TODO: logging
            raise TypeError
        return

    def start(self) -> None:
        try:
            self.client_registry.start()
        except Exception as e:
            self.logger.info(f"Unexpected error while starting client: {str(e)}")
        return

    def ticker(
        self,
        callback: Callable,
    ) -> None:
        for key in self.client_registry.registry:
            try:
                self.client_registry.registry[key].ticker(
                    callback = callback,
                    trade_pair = self.trade_pair,
                )
            except Exception as e:
                self.logger.critical(f"Unexpected Error while subscribing to ticker: {str(e)}")
        return

    def kline(
        self,
        callback: Callable,
    ) -> None:
        for key in self.client_registry.registry:
            try:
                self.client_registry.registry[key].kline(
                    callback=callback,
                    trade_pair=self.TradePair,
                )
            except Exception as e:
                self.logger.critical(f"Unexpected Error while subscribing to kline: {str(e)}")
        return

    def depth(
        self,
        callback: Callable,
    ) -> None:
        for key in self.client_registry.registry:
            try:
                self.client_registry.registry[key].depth(
                    callback=callback,
                    trade_pair=self.TradePair,
                )
            except Exception as e:
                self.logger.critical(f"Unexpected Error while subscribing to depth/orderBook: {str(e)}")
        return
