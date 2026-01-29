from service.sdk.websocket_sdk import WebSocketClient
from src.object.trade import TradePair


class WebSocketClientRegistry:
    def __init__(
        self,
        name: str,
    ) -> None:
        self._registry: dict[str, WebSocketClient] = dict()
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

    @property
    def registry(self):
        return self._registry


class WebSocketInterface:
    def __init__(
        self,
        client_registry: WebSocketClientRegistry,
        trade_pair: TradePair | None = None,
    ) -> None:
        self.trade_pair = TradePair("BTC", "USDT") if trade_pair is None else trade_pair

        self.client_registry = client_registry
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
