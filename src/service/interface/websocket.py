from service.sdk.websocket_sdk import WebSocketClient


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
    def __init__(self) -> None:
        return
