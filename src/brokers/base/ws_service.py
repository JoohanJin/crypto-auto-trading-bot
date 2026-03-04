# Built-in Library
import time
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import websocket

from src.infrastructure.logging.set_logger import get_adapter, get_logger


if TYPE_CHECKING:
    import threading


logger = get_logger(__name__)


class WebSocket(ABC):
    _instance_counter: int = 1  # shared across all instance

    @classmethod
    def _generate_id(cls) -> int:
        cls._instance_counter += 1
        return (cls._instance_counter - 1)

    def _operation_logging(
        self,
        log: str,
    ) -> None:
        log = str(log)
        self.logger.info(f"[SUCCESS] _operation_logging() | Response Type: {type(log).__name__}")

    def generate_timestamp(self) -> int:
        return int(time.time() * 1_000)

    def __init__(
        self,
        name: str,
        api_key: str | None,
        secret_key: str | None,
        ping_interval: int,  # in seconds -> every <ping_interval> send the hearbeat
        url: str | None = None,
    ) -> None:
        # wss endpoint
        self.url: str = url

        # instance specific identifier
        self._id: int = self._generate_id()
        self.name: str = name
        self.logger = get_adapter(logger, f"{self.__class__.__name__}_{self.name}")

        self.logger.info(f"[SERVICE_INIT] {self.name} initialized")

        # api_key and secret_key
        self.api_key: str = api_key
        self.secret_key: str = secret_key
        self.authenticated: bool | None = None

        # ping interval
        self.ping_interval: int = ping_interval

        # threads list
        self.threads: list[threading.Thread] = []


    '''
    ####################################################################################
    #                            Instance Specific Field                               #
    ####################################################################################
    '''
    @property
    def id(self) -> int:
        return self._id

    '''
    ####################################################################################
    #                                Abstract Method                                   #
    ####################################################################################
    '''

    @abstractmethod
    def connect(self) -> None:
        '''
        ;func connect()
            - connect to the endpoint
        '''
        return

    @abstractmethod
    def disconnect(self) -> None:
        '''
        ;func disconnect()
            - close WebSocket connection gracefully.
        '''
        return

    @abstractmethod
    def subscribe(self) -> None:
        '''
        ;func subscribe()
            - subscribe to the topic/data stream
        '''
        return

    @abstractmethod
    def unsubscribe(self) -> None:
        '''
        ;func unsubscribe()
            - unsubscribe from the topic/data stream
        '''
        return

    @abstractmethod
    def send(self) -> None:
        '''
        ;func send()
            - send message to the server/endpoint
        '''
        return

    @abstractmethod
    def _reconnect(self) -> None:
        '''
        ;func _reconnect()
            - reconnect to the endpoint once it is closed
        '''
        return

    '''
    ####################################################################################
    #                       Abstract Method - WebSocketApp                             #
    ####################################################################################
    '''
    @abstractmethod
    def on_open(
        self,
        ws: websocket.WebSocketApp,
    ) -> None:
        return

    @abstractmethod
    def on_message(
        self,
        ws: websocket.WebSocketApp,
        msg: str | bytes,
    ) -> None:
        return

    @abstractmethod
    def on_close(
        self,
        ws: websocket.WebSocketApp,
        status_cod: int,
        close_msg: int,
    ) -> None:
        return

    @abstractmethod
    def on_error(
        self,
        ws: websocket.WebSocketApp,
        error: Exception,
    ) -> None:
        return
