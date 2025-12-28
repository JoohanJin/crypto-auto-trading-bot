# Built-in Library
from typing import Callable

# Custom Library
from sdk.websocket_sdk import BasicWebSocketManager

# get the Logger
from logger.set_logger import operation_logger


# MexC Future Websocket Manager
class _FutureWebSocketManager(BasicWebSocketManager):
    def __init__(
        self: "_FutureWebSocketManager",
        ws_name: str = "FutureWebSocketV1",
        api_key: str | None = None,
        secret_key: str | None = None,
        endpoint: str | None = "wss://contract.mexc.com/edge",
        ping_interval: int = 5,  # Second
        connection_interval: int = 10,  # ?
        ping_timeout: int = 10,
        conn_timeout: int = 30,
        default_callback: Callable | None = None,
    ):
        # BasicWebSocketManager.init()
        kwargs: dict = dict(
            ws_name=ws_name,
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

        # if there is no default function.
        self.callback_function = self._deal_with_response

        return

    def _deal_with_response(
        self: "_FutureWebSocketManager",
        msg: str,
    ):
        # comprehensive callback function which can deal with all of the message
        """
        Types of Response
            # auth_message
            # subscribe response
            # pong
        """

        '''
        # Message Classification Sub-Function.
        '''
        # Authententication ack or nack
        def is_auth_response():
            if msg.get("channel") == "rs.login":
                return True
            return False

        # SUbscription ack or nack
        def is_sub_response():
            if str(msg.get("channel", "")).startswith("rs.sub."):
                return True
            return False

        # ping-pong for connection maintainining
        def is_pong_msg():
            if msg.get("channel", "") == "pong":
                return True
            return False

        # error message
        def is_error_msg():
            if msg.get("channel", "") == "rs.error":
                return True
            return False
        '''
        # END of Message Classification Sub-Function.
        '''

        if is_auth_response():
            self._deal_with_auth_msg(msg=msg)
        elif is_sub_response():
            self._deal_with_sub_msg(msg=msg)
        elif is_error_msg():
            operation_logger.info(
                f"{__name__} - func _deal_with_response(): The error has been received from the host: {msg}"
            )
        elif is_pong_msg():  # Do Nothing
            pass
        else:
            self._deal_with_normal_msg(msg=msg)

        return

    def _deal_with_auth_msg(self, msg):
        """
        Determine if the login has been successful.
        # notify the result to the user by operation_logger.
        """
        if msg.get("data") == "success":  # login success
            operation_logger.info(
                f"Authorization for {self.ws_name} has been successful."
            )
            self.auth = True
        else:  # login fail
            operation_logger.debug(
                f"Authoriztion for {self.ws_name} has not been successful."
                f"Please check your keys!"
            )
        return

    def _deal_with_sub_msg(self, msg):
        # TODO: refactor websocket base class with try-catch block for better error handling.
        topic = msg.get("channel")

        if (
            msg.get("channel", "").startswith("rs.")
            or msg.get("channel", "").startswith("push.")
        ) and msg.get("channel", "") != "rs.error":
            operation_logger.info(
                f"{__name__} - func _dealwith_sub_msg(): Subcription to {topic} has been establisehd"
            )
        else:
            operation_logger.info(
                f"{__name__} - func _dealwith_sub_msg(): Subscription to {topic} has failed to establish."
            )

        return

    def _deal_with_normal_msg(self, msg):
        topic = msg.get("channel").replace("push.", "").replace("sub.", "")

        callback_function = self._get_callback(topic)

        if (callback_function):  # if callback_function is not None.
            callback_function(msg)

        return

    def _check_callback(self, topics):
        for topic in topics:
            if topic in self.callback_dictionary:
                operation_logger.info(
                    f"{__name__} - func _deal_with_normal_msg(): {topic} is already subscribed"
                )
                raise Exception


# TODO: remove inheritance -> at least check it -> not sure why inhertiance is needed at this point.
class _FutureWebSocket(_FutureWebSocketManager):
    def __init__(
        self: "_FutureWebSocket",
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
