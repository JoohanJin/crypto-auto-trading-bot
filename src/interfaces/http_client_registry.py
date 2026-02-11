from src.brokers.base.http_client import HttpClient
from src.interfaces.base.base_registry import BaseClientRegistry


class HttpClientRegistry(BaseClientRegistry[HttpClient]):
    def __init__(self, name: str | None = None) -> None:
        super().__init__(name=name if name else "HTTP_CLIENT_REGISTRY")
