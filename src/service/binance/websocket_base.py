# Standard Library
import base64
import json
import time
from typing import Callable
import threading
from urllib.parse import urlencode

import websocket
from cryptography.hazmat.primitives.serialization import load_pem_private_key

from service.sdk.websocket_sdk import BasicWebSocketClient
from logger.set_logger import operation_logger


class UserWebSocketClient(BasicWebSocketClient):
    def generate_method_id(self) -> int:
        return self.generate_timestamp()

    def __repr__(self):
        return f"Binance_UserWebSocketClient:{self.name}"

    def __init__(
        self,
        api_key: str,
        secret_key: str,
        ping_interval: int | None,
        url: str = "wss://ws-fapi.binance.com/ws-fapi/v1",  # User Stream
        default_callback: Callable | None = None,
        name: str = None,
    ) -> None:
        super().__init__(
            name=name or f"Binance_User_WebSocket_Client_{self.id}",
            url=url,
            api_key=api_key,
            secret_key=secret_key,
            ping_interval=ping_interval,
        )

        self.private_key = None
        if secret_key:
            # Load from PEM content string
            self.private_key = load_pem_private_key(
                data=secret_key.encode('utf-8'),
                password=None
            )

        self.callbacks_lock : threading.Lock = threading.Lock()

        self.subscriptions_lock: threading.Lock = threading.Lock()
        self.subscriptions: dict[int, dict] = dict()  # {id: str | bytes} to be sent

        self.default_callback: Callable = default_callback
        self._authenticated: bool = False

        # threading Event
        self._thread_stop: threading.Event = threading.Event()
        self._thread_pause: threading.Event = threading.Event()
        self._connection_ready: threading.Event = threading.Event()
        self._intentional_close: threading.Event = threading.Event()

        # Lock
        self._reconnect_lock: threading.Lock = threading.Lock()

        # WebSocketApp
        self.ws: websocket.WebSocketApp = self._construct_wsa()
        return

    def _is_connected(self) -> bool:
        try:
            if (self.ws and self.ws.sock and self.ws.sock.connected):
                return True
        except Exception as e:
            operation_logger.critical(
                f"{__name__} - {self.__class__.__name__} - {self.name} - "
                f"Unexpected problem whic checking the connection state: {str(e)}"
            )
        return False

    def start(self) -> None:
        self.connect()

    def send(
        self,
        data: str | bytes,
    ) -> None:
        if isinstance(data, dict):
            payload = json.dumps(data)

            try:
                if self._is_connected():
                    self.ws.send(payload)
            except Exception as e:
                operation_logger.info(
                    f"{__name__} - {self.__class__.__name__} - {self.name} - Unexpected error while authenticating: "
                    f"{str(e)}"
                )
        else:
            operation_logger.critical(
                f"{__name__} - {self.__class__.__name__} - {self.name} - type of the data passed is not dictionary."
            )
            raise
        return

    def _authenticate(self) -> None:
        '''
        user_ws: websocket.WebSocketApp = self.wss[1]
        {
            "id": <ts>,
            "method": "session.logon",
            "params": {
                "apiKey": <api-key>,
                "signature": <signature>,
                "timestamp": <ts>
            }
        }
        '''
        id: int = self.generate_timestamp()

        params = dict(
            apiKey=self.api_key,
            timestamp=id,
        )

        signature: str = self._generate_signature(params)

        params["signature"] = signature

        payload: dict = dict(
            id=id,
            method="session.logon",
            params=params,
        )

        with self.callbacks_lock:
            self.callbacks[id] = self._update_authenticated
        try:
            self.send(payload)
            time.sleep(1)
            return
        except Exception as e:
            operation_logger.critical(
                f"{__name__} - {self.__class__.__name__} - Binance WebSocket has unexpected error: {str(e)}"
            )
        return

    def _update_authenticated(self, data: dict | list) -> None:
        if isinstance(data, dict):
            if data.get('status', None) == 200:
                self._authenticated = True
                operation_logger.info(
                    f"{__name__} - {self.__class__.__name__} - {self.name} - "
                    f"Authentication to {self.url} has been successful."
                )
        else:
            operation_logger.critical(
                f"{__name__} - {self.__class__.__name__} - {self.name} - "
                f"Authentication to {self.url} has not been successful."
            )
            raise TypeError("authentication msg format is wrong.")
        return

    def _generate_signature(
        self,
        params: dict,
    ) -> str:
        # sort params based on the key
        query_str: str = urlencode(sorted(params.items()))

        # Sign with Ed25519 private key and base64 encode
        signature = self.private_key.sign(query_str.encode('ASCII'))
        return base64.b64encode(signature).decode('ASCII')

    def _thread_sending_requests(
        self,
    ) -> None:
        while not self._thread_stop.is_set():
            # Skip if paused
            if self._thread_pause.is_set():
                time.sleep(0.5)
                continue

            with self.subscriptions_lock:
                tmp_subs: dict[int, dict] = self.subscriptions.copy()
            for id in tmp_subs:
                if self._thread_stop.is_set():
                    break
                self._construct_params(tmp_subs[id]["params"])
                self.send(tmp_subs[id])
            time.sleep(2)
        return

    def _construct_params(self, params: dict) -> dict:
        # Remove old signature before regenerating (signature should not be part of signed payload)
        params.pop("signature", None)
        params["apiKey"] = self.api_key
        params["timestamp"] = self.generate_timestamp()
        params["signature"] = self._generate_signature(params)

    '''
    ####################################################################################
    #                                    Threads                                     #
    ####################################################################################
    '''
    def _initialize_threads(self) -> None:
        self.threads.append(
            threading.Thread(
                name=f"{self.name}_connection_thread",
                target=self.ws.run_forever,
                kwargs={'ping_interval': 0},
                daemon=True,
            )
        )

        self.threads.append(
            threading.Thread(
                name=f"{self.name}_custom_stream_thread",
                target=self._thread_sending_requests,
                daemon=True,
            )
        )
        return

    def _start_threads(self) -> None:
        for thread in self.threads:
            try:
                thread.start()
                operation_logger.info(
                    f"{__name__} - {self.__class__.__name__} - {self.name} - "
                    f"{thread.name} has been started successfully."
                )
            except Exception as e:
                operation_logger.critical(
                    f"{__name__} - {self.__class__.__name__} - {self.name}- "
                    f"{thread.name} has not been started successfully: {str(e)}"
                )
                raise
        return

    def _clean_up_connections(self) -> None:
        operation_logger.info(
            f"{__name__} - {self.__class__.__name__} - {self.name} - Cleaning up {len(self.threads)} threads."
        )

        self._thread_stop.set()

        try:
            if self._is_connected():
                self.ws.close()
            else:
                operation_logger.critical(
                    f"{__name__} - {self.__class__.__name__} - {self.name} - "
                    f"WebSocket already closed."
                )
        except Exception as e:
            operation_logger.critical(
                f"{__name__} - {self.__class__.__name__} - {self.name} - "
                f"Unexpected Error during close: {str(e)}"
            )

        self.threads.clear()
        self._thread_stop.clear()
        self.ws = None
        return

    def _handle_reconnect(
        self,
        retry_delay: float = 3.0,
    ):
        # Give the old websocket_connection thread time to fully exit
        time.sleep(0.5)

        while True:
            if self._intentional_close.is_set():
                operation_logger.info(
                    f"{__name__} - {self.__class__.__name__} - Binance User WebSocket - "
                    f"Intentional close detected during reconnect, aborting."
                )
                return

            try:
                operation_logger.info(
                    f"{__name__} - {self.__class__.__name__} - Binance User WebSocket - Attempting reconnection..."
                )

                self._reconnect()

            except Exception as e:
                operation_logger.warning(
                    f"{__name__} - {self.__class__.__name__} - Binance WebSocket - Reconnection attempt failed: {str(e)}"
                )

            # Wait before next attempt
            operation_logger.info(
                f"{__name__} - {self.__class__.__name__} - Binance WebSocket - "
                f"Waiting {retry_delay}s before next reconnect attempt..."
            )
            time.sleep(retry_delay)
        return

    '''
    ####################################################################################
    #                                    Overriden                                     #
    ####################################################################################
    '''
    def connect(self) -> None:
        self._initialize_threads()
        self._start_threads()
        return

    def disconnect(self) -> None:
        if self._is_connected():
            self.ws.close()
            self._intentional_close.set()
        return

    def subscribe(
        self,
        method: str,
        callback_function: Callable,
        params: dict | None = None,
    ) -> None:
        id: int = self.generate_method_id()

        if params is None:
            params = dict()

        payload = dict(
            id = id,
            method = method,
            params = params,
        )

        with self.callbacks_lock :
            self.callbacks[id] = callback_function

        with self.subscriptions_lock:
            self.subscriptions[id] = payload

        return

    def unsubscribe(self) -> None:
        return

    def _resubscribe(self) -> None:
        return

    def _reconnect(self) -> None:
        # Prevent concurrent reconnection attempts
        if not self._reconnect_lock.acquire(blocking=False):
            operation_logger.info(
                f"{__name__} - {self.__class__.__name__} - Reconnection already in progress, skipping."
            )
            return

        try:
            operation_logger.info(
                f"{__name__} - {self.__class__.__name__} - Starting reconnection process..."
            )

            # Signal threads to stop
            self._thread_stop.set()
            self._connection_ready.clear()

            # Don't try to close the socket here - it's already closed when on_close is called
            # Just clean up threads (skipping the current one if called from on_close)
            self._clean_up_connections()

            # Now reconnect
            self.connect()
        finally:
            self._reconnect_lock.release()
        return

    def authenticate(self) -> None:
        """Public API for authentication. Delegates to _authenticate()."""
        self._authenticate()
        return

    '''
    ####################################################################################
    #                           Overriden - WebSocketApp                               #
    ####################################################################################
    '''
    def on_open(
        self,
        ws: websocket.WebSocketApp,
    ) -> None:
        operation_logger.info(
            f"{__name__} - {self.__class__.__name__} - {self.name}"
            f"WebSocket has been opened and made a connection to {ws.url} [v]"
        )
        return

    def on_message(
        self,
        ws: websocket.WebSocketApp,
        msg: str | bytes,
    ) -> None:
        data = json.loads(msg)
        method_id = data.get("id")

        if method_id and isinstance(method_id, int):
            with self.callbacks_lock :
                callback = self.callbacks.get(method_id, None)

            if isinstance(callback, Callable):
                callback(data)
        return

    def on_close(
        self,
        ws: websocket.WebSocketApp,
        status_code: int,
        close_msg: str,
    ) -> None:
        operation_logger.warning(
            f"{__name__} - {self.__class__.__name__} - Binance WebSocket has been closed with {status_code}: {close_msg}"
        )

        if self._intentional_close.is_set():
            self._intentional_close.clear()
            return

        else:
            operation_logger.info(
                f"{__name__} - {self.__class__.__name__} - {self.name} - Accidential Websocket closure Detected. "
                f"Spawining a reconnection thread."
            )
        # handle reconnection logic
            reconnection_thread: threading.Thread = threading.Thread(
                name=f"{self.name}_reconnection_thread",
                target=self._handle_reconnect,
                daemon=True,
            )
            reconnection_thread.start()
        return

    def on_error(
        self,
        ws: websocket.WebSocketApp,
        error: Exception,
    ) -> None:
        return

    def on_ping(
        self,
        ws: websocket.WebSocketApp,
        data: str | bytes,
    ) -> None:
        # Send pong response via underlying socket
        ws.sock.pong(data)
        operation_logger.debug(
            f"{__name__} - {self.__class__.__name__} - Binance WebSocket API: Sent pong response to {ws.url}"
        )
        return

    '''
    ####################################################################################
    #                                    WebSocketApp                                  #
    ####################################################################################
    '''
    def _construct_wsa(
        self,
        on_open: Callable | None = None,
        on_close: Callable | None = None,
        on_message: Callable | None = None,
        on_error: Callable | None = None,
    ) -> websocket.WebSocketApp | None:
        def on_open_wrapper(ws: websocket.WebSocketApp):
            self._connection_ready.set()

            (on_open or self.on_open)(ws)
            return

        return websocket.WebSocketApp(
            url = self.url,
            on_open=on_open_wrapper,
            on_close=on_close or self.on_close,
            on_message=on_message or self.on_message,
            on_error=on_error or self.on_error,
            on_ping=self.on_ping,
        )


class MarketWebSocketClient(BasicWebSocketClient):
    def __repr__(self):
        return f"Binance_MarketWebSocketClient: {self.name}"

    def __init__(
        self,
        ping_interval: int | None,
        url: str = "wss://fstream.binance.com/ws",  # Market Stream
        default_callback: Callable | None = None,
        name: str = None,
    ) -> None:
        super().__init__(
            name=name or f"Binance_Market_WebSocket_Client_{self.id}",
            url=url,
            api_key=None,
            secret_key=None,
            ping_interval=ping_interval,
        )

        self.default_callback = default_callback
        return


class TradingWebSocketClient(BasicWebSocketClient):
    def __init__(self) -> None:
        return
