# Standard Library
from collections.abc import Callable

# Custom Library
from src.brokers.base.ws_client import WebSocketClient
from src.core.models.trade import TradePair
from src.infrastructure.logging.set_logger import get_logger
from src.interfaces.base.base_interface import BaseInterface
from src.interfaces.ws_client_registry import WebSocketClientRegistry


logger = get_logger(__name__)


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

        self.logger.info(f"[SERVICE_INIT] {self.name} initialized")

    def push_client(
        self,
        key: str,
        client: WebSocketClient,
    ) -> None:
        if isinstance(client, WebSocketClient):
            super().push_client(key, client)
        else:
            raise TypeError(f"Expected WebSocketClient, got {type(client)}")

    def start(self) -> None:
        try:
            self.client_registry.start()
        except Exception as e:
            self.logger.info(f"[SERVICE_INIT_ERROR] {self.name} | Failed to start client | Error: {type(e).__name__}: {e!s}")

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
                self.logger.critical(f"[WS_SUBSCRIBE] {self.name} | Error: {type(e).__name__}: {e!s}")

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
                self.logger.critical(f"[WS_SUBSCRIBE] {self.name} | Error: {type(e).__name__}: {e!s}")

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
                self.logger.critical(f"[WS_SUBSCRIBE] {self.name} | Error: {type(e).__name__}: {e!s}")
