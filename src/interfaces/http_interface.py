from src.brokers.base.http_sdk import HttpClient
from src.interfaces.base.base_registry import BaseClientRegistry
from src.interfaces.base.base_interface import BaseInterface


class HttpClientRegistry(BaseClientRegistry[HttpClient]):
    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name if name else "HTTP_CLIENT_REGISTRY")


class HttpInterface(BaseInterface[HttpClientRegistry, HttpClient]):
    def __init__(
        self,
        name: str | None = None,
        client_registry: HttpClientRegistry | None = None,
    ) -> None:
        registry = (
            client_registry
            if client_registry
            else HttpClientRegistry(name=f"{name.upper()}_REGISTRY" if name else "HTTP_CLIENT_INTERFACE_REGISTRY")
        )
        
        super().__init__(
            client_registry=registry,
            name=name.upper() if name else "HTTP_CLIENT_INTERFACE"
        )

    def push_client(self, key: str, client: HttpClient) -> None:
        if isinstance(client, HttpClient):
            super().push_client(key, client)
        else:
            raise TypeError(f"Expected HttpClient, got {type(client)}")
