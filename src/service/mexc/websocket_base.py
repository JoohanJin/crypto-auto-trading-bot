# Built-in Library
from typing import Callable

# Custom Library
from sdk.websocket_sdk import _FutureWebSocketManager

# get the Logger
from logger.set_logger import operation_logger


# MexC Future Websocket Manager
class _FutureWebSocket(_FutureWebSocketManager):
    def __init__(
        self,
        endpoint: str = "wss://contract.mexc.com/edge",
        ws_name: str = "FutureMarketWebSocketV1",
        api_key: str | None = None,
        secret_key: str | None = None,
        ping_interval: int = 5,  # Second
        connection_interval: int = 10,  # ?
        ping_timeout: int = 10,
        conn_timeout: int = 30,
        default_callback: Callable | None = None,
    ):
        """ """
        self.ws_name = ws_name
        self.endpoint = endpoint

        self.active_connections = []

        kwargs = dict(
            api_key=api_key,
            secret_key=secret_key,
            endpoint=endpoint,
            ping_interval=ping_interval,
            connection_interval=connection_interval,
            ping_timeout=ping_timeout,
            conn_timeout=conn_timeout,
            default_callback=default_callback,
        )

        super().__init__(**kwargs)

        self.private_topics = [
            "personal.order",
            "personal.asset",
            "personal.position",
            "personal.risk.limit",
            "personal.adl.level",
            "personal.position.mode",
        ]

        # initialize the WebSocket for Future End-point
        self.__initialize_websocket()

        return

    def __initialize_websocket(
        self,
    ):
        """ """
        try:
            # self.ws = _FutureWebSocketManager(
            #     self.ws_name,
            #     api_key = self.api_key,
            #     secret_key = self.secret_key,
            # )
            self._connect()
        except Exception as e:
            operation_logger.error(f"{__name__} - func initialize_websocket(): {e}")
            print(f"{__name__} - func initialize_websocket(): {e}")
            return

        return

    def is_connected(self):
        """ """
        return self._are_connections_connected(self.active_connections)
