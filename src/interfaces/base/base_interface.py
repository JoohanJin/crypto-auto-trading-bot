from typing import Generic, TypeVar
from src.interfaces.base.base_registry import BaseClientRegistry
from src.infrastructure.logging.set_logger import get_logger, get_adapter

logger = get_logger(__name__)

TClient = TypeVar("TClient")
TRegistry = TypeVar("TRegistry", bound=BaseClientRegistry)


class BaseInterface(Generic[TRegistry, TClient]):
    def __init__(
        self,
        client_registry: TRegistry,
        name: str | None = None,
    ) -> None:
        self.name: str = name if name else self.__class__.__name__
        self.client_registry: TRegistry = client_registry
        self.logger = get_adapter(logger, f"{self.__class__.__name__}_{self.name}")
        return

    def push_client(self, key: str, client: TClient) -> None:
        # Assuming TRegistry has a push method matching BaseClientRegistry signature
        self.client_registry.push(key, client)

    def get_client(self, key: str) -> TClient | None:
        return self.client_registry.get(key)

    def pop_client(self, key: str) -> None:
        if self.client_registry.get(key):
            self.client_registry.pop(key)
