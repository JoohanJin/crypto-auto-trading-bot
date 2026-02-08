# Standard Library
from collections.abc import Callable

# Custom Library
from src.brokers.base.ws_sdk import WebSocketClient
from src.core.models.trade import TradePair
from src.infrastructure.logging.set_logger import operation_logger


class WebSocketClientRegistry:
    def __init__(
        self,
        name: str | None,
    ) -> None:
        self._registry: dict[str, WebSocketClient] = dict()
        self.name: str = "WebSocketClientRegistry" if name is None else name
        return

    def push(
        self,
        key: str,
        client: WebSocketClient,
    ) -> None:
        self._registry[key] = client
        return

    def get(
        self,
        key: str,
    ) -> WebSocketClient | None:
        return self._registry.get(key, None)

    def pop(
        self,
        key: str,
    ) -> None:
        self._registry.pop(key, None)
        return

    def start(self) -> None:
        for key in self._registry:
            try:
                if hasattr(self._registry[key], 'start'):
                    self._registry[key].start()
            except Exception as e:
                operation_logger.warning(
                    f"{__name__} - {self.__class__.__name__} - {self.name}: {str(e)}"
                )
        return

    @property
    def registry(self):
        return self._registry


class WebSocketInterface:
    def __init__(
        self,
        client_registry: WebSocketClientRegistry | None = None,
        trade_pair: TradePair | None = None,
        name: str | None = None,
    ) -> None:
        self.trade_pair = TradePair("BTC", "USDT") if trade_pair is None else trade_pair
        self.client_registry = (
            client_registry
            if client_registry
            else WebSocketClientRegistry(name="DEFAULT_WEBSOCKET_CLIENT_REGISTRY")
        )

        self.name: str = "WebSocketInterface" if name is None else name

        operation_logger.info(
            f"{__name__} - {self.__class__.__name__} - {self.name} has been initialized."
        )
        return

    def push_client(
        self,
        key: str,
        client: WebSocketClient,
    ) -> None:
        if isinstance(client, WebSocketClient):
            self.client_registry.push(key, client)
        else:
            # TODO: logging
            raise TypeError
        return

    def get_client(
        self,
        key: str,
    ) -> WebSocketClient | None:
        return self.client_registry.get(key, None)

    def pop_client(
        self,
        key: str,
    ) -> None:
        if self.client_registry.get(key, None):
            self.client_registry.pop(key)
            return
        return

    def start(self) -> None:
        try:
            self.client_registry.start()
        except Exception as e:
            operation_logger.info(
                f"{__name__} - {self.__class__.__name__} - {self.name} - Unexpected error while starting client: "
                f"{str(e)}"
            )
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
                operation_logger.crticial(
                    f"{__name__} - {self.__class__.__name__} - {self.name} - "
                    f"Unexpected Error while subscribing to ticker: {str(e)}"
                )
        return

    def kline(
        self,
        callback: Callable,
    ) -> None:
        for key in self.client_registry:
            try:
                self.client_registry.registry[key].kline(
                    callback=callback,
                    trade_pair=self.TradePair,
                )
            except Exception as e:
                operation_logger.crticial(
                    f"{__name__} - {self.__class__.__name__} - {self.name} - "
                    f"Unexpected Error while subscribing to kline: {str(e)}"
                )
        return

    def depth(
        self,
        callback: Callable,
    ) -> None:
        for key in self.client_registry:
            try:
                self.client_registry.registry[key].depth(
                    callback=callback,
                    trade_pair=self.TradePair,
                )
            except Exception as e:
                operation_logger.crticial(
                    f"{__name__} - {self.__class__.__name__} - {self.name} - "
                    f"Unexpected Error while subscribing to depth/orderBook: {str(e)}"
                )
        return
