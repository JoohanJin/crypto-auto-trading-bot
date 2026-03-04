# from queue import Queue
from typing import Generic, TypeVar
from abc import ABC, abstractmethod
import queue

T = TypeVar('T')


class BasePipeline(ABC, Generic[T]):
    @abstractmethod
    def __init__(self) -> None:
        self.queue: queue.Queue[T] = queue.Queue()
        return

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
