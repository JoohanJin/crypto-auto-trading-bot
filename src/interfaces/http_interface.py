from src.brokers.base.http_sdk import HttpClient


class HttpClientRegistry:
    def __init__(self, name: str) -> None:
        self._registry: dict[str, HttpClient]
        return

    def push(self) -> None:
        return

    def get(self) -> None:
        return
    
    def pop(
        self,
    ) -> None:
        return

    @property
    def registry(self):
        return self._registry


class HttpInterface:
    def __init__(
        self,
        name: str,
        client_registry: HttpClientRegistry | None = None,
    ) -> None:
        self.name: str = name

        self.client_registry: HttpClientRegistry = (
            client_registry
            if client_registry
            else HttpClientRegistry(name=f"{name.upper()}_REGISTRY")
        )
        return

    def push_client(self):
        return

    def get_client(self):
        return

    def pop_client(self):
        return
