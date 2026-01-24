# Built-in Library
from abc import ABC, abstractmethod
import time
import threading
import websocket

from logger.set_logger import operation_logger


class BasicWebSocketClient(ABC):
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
        operation_logger.info(log)

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
        self._name: str = name

        # api_key and secret_key
        self.api_key: str = api_key
        self.secret_key: str = secret_key
        self.authenticated: bool | None = None

        # ping interval
        self.ping_interval: int = ping_interval

        # threads list
        self.threads: list[threading.Thread] = list()

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


class WebSocketClient(ABC):
    '''
    ;class WebSocketClient
        - Base Class for WebSocket Client for each broker
        - It defines the contract "each WebSocket for Crypto Broker should have"
    '''
    def __init__(self) -> None:
        self.ws: BasicWebSocketClient
        return

    '''
    ####################################################################################
    #                                 Market Stream                                      #
    ####################################################################################
    '''
    @abstractmethod
    def ticker(self) -> None:
        '''
        ;func ticker
        '''
        return

    @abstractmethod
    def kline(self) -> None:
        return

    @abstractmethod
    def depth(self) -> None:
        '''
        ;func depth()
            - return the depth of the market, i.e., Order Book Depth
            - The entire collection of Bids and Asks for the given contract, organized by price.

        ;The market's ability to sustain relatively large market orders without impacting the price of the security.
        ;The list of all pending limit orders waiting to be executed.
        '''
        return

    '''
    ####################################################################################
    #                                 User Stream                                      #
    ####################################################################################
    '''

    '''
    ####################################################################################
    #                                    Trade                                         #
    ####################################################################################
    '''
