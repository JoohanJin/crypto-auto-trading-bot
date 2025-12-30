# Built-in Library
from abc import ABC, abstractmethod
from typing import Callable
import time
import websocket
import threading

# Get the logger


class BasicWebSocketManager(ABC):
    _intance_counter: int = 0  # shared across all instance

    @classmethod
    def _generate_id(cls) -> int:
        cls._instance_counter += 1
        return cls._instance_counter

    @staticmethod
    def generate_timestamp() -> int:
        return int(time.time() * 1_000)

    def __init__(
        self,
        url: str,
        name: str,
        api_key: str | None,
        secret_key: str | None,
        ping_interval: int = 20,  # in seconds -> every <ping_interval> send the hearbeat

    ) -> None:
        # wss endpoint
        self.url: str = url

        # instance specific identifier
        self._id: int = self._generate_id()
        self._name: str = name

        # api_key and secret_key
        self.api_key: str = api_key
        self.secret_key: str = secret_key
        self.authenticated: bool | None = None

        # ping interval
        self.ping_interval: int = ping_interval

        # threads list
        self.threads: list[threading.Thread] = list()

        # callback function map based on the topics
        self.callbacks: dict[str, Callable] = dict()

        return

    '''
    ####################################################################################
    #                            Instance Specific Field                               #
    ####################################################################################
    '''
    @property
    def id(self) -> int:
        return self._id

    @property
    def name(self) -> str:
        return self._name

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
    def subscribe(
        self,
        topic,
        callback_function,
        param,
    ) -> None:
        '''
        ;func subscribe()
            - subscribe to the topic/data stream
        '''
        return

    @abstractmethod
    def unsubscribe(self, topic) -> None:
        '''
        ;func unsubscribe()
            - unsubscribe from the topic/data stream
        '''
        return

    @abstractmethod
    def send(self, msg: str | bytes) -> None:
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

    @abstractmethod
    def _heartbeat(self) -> None:
        '''
        ;func _heartbeat()
            - send heartbeat signal
            - can be ping or pong
        '''
        return

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
        msg: str | bytes
    ) -> None:
        return

    @abstractmethod
    def on_close(
        self,
        ws: websocket.WebSocketApp,
        status_code: int,
        close_msg: str,
    ) -> None:
        return

    @abstractmethod
    def on_error(
        self,
        ws: websocket.WebSocketApp,
        error: Exception,
    ) -> None:
        return

    @abstractmethod
    def on_ping(
        self,
        ws: websocket.WebSocketApp,
        data: bytes,
    ) -> None:
        return
