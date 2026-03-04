# from queue import Queue
import queue
from abc import ABC, abstractmethod
from typing import Generic, TypeVar


T = TypeVar("T")


class BasePipeline(ABC, Generic[T]):
    @abstractmethod
    def __init__(self) -> None:
        self.queue: queue.Queue[T] = queue.Queue()

    @abstractmethod
    def push(
        self,
        *args,
        **kwargs,
    ) -> bool:
        return False

    @abstractmethod
    def pop(
        self,
        *args,
        **kwagrs,
    ) -> T | None:
        return
