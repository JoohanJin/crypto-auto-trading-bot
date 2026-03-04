from typing import Generic, TypeVar

from src.infrastructure.logging.set_logger import get_adapter, get_logger


logger = get_logger(__name__)
T = TypeVar("T")


class BaseClientRegistry(Generic[T]):
    def __init__(self, name: str | None = None) -> None:
        self.name: str = name if name else self.__class__.__name__
        self._registry: dict[str, T] = {}
        self.logger = get_adapter(logger, f"{self.__class__.__name__}_{self.name}")

        self.logger.info(f"[COMPONENT_INIT] {self.name} initialized")

    def push(self, key: str, client: T) -> None:
        self._registry[key] = client

    def get(self, key: str) -> T | None:
        return self._registry.get(key, None)

    def pop(self, key: str) -> None:
        self._registry.pop(key, None)

    @property
    def registry(self) -> dict[str, T]:
        return self._registry
