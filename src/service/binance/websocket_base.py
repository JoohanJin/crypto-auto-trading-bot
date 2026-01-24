# Standard Library
import base64
import json
import time
import threading
from urllib.parse import urlencode
from collections.abc import Callable

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
            name=name or "Binance_User_WebSocket_Client",
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

        # callback function map based on the topics
        self.callbacks_lock : threading.Lock = threading.Lock()
        self.callbacks: dict[str | int, Callable] = dict()

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
                time.sleep(1.0)
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
                    f"No need to close the WebSocket since the WebSocket already closed."
                )
        except Exception as e:
            operation_logger.critical(
                f"{__name__} - {self.__class__.__name__} - {self.name} - "
                f"Unexpected Error during close: {str(e)}"
            )

        self.threads.clear()
        self._thread_stop.clear()
        return

    def _handle_reconnect(
        self,
        retry_delay: float = 3.0,
    ):
        # Give the old websocket_connection thread time to fully exit
        time.sleep(0.5)

        while not self._is_connected():
            if self._intentional_close.is_set():
                operation_logger.info(
                    f"{__name__} - {self.__class__.__name__} - {self.name} - "
                    f"Intentional close detected during reconnect, aborting."
                )
                return

            try:
                operation_logger.info(
                    f"{__name__} - {self.__class__.__name__} - {self.name} - Attempting reconnection..."
                )

                self._reconnect()

                # Wait for connection to be ready
                if self._connection_ready.wait(timeout=10.0):
                    self._resubscribe()
                    operation_logger.info(
                        f"{__name__} - {self.__class__.__name__} - {self.name} - "
                        f"Reconnection completed successfully."
                    )
                    return

            except Exception as e:
                operation_logger.warning(
                    f"{__name__} - {self.__class__.__name__} - {self.name} - Reconnection attempt failed: {str(e)}"
                )

            # Wait before next attempt
            operation_logger.info(
                f"{__name__} - {self.__class__.__name__} - {self.name} - "
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
            elif isinstance(self.default_callback, Callable):
                self.default_callback(data)
            else:
                self._operation_logging(data)
        return

    def on_close(
        self,
        ws: websocket.WebSocketApp,
        status_code: int,
        close_msg: str,
    ) -> None:
        operation_logger.warning(
            f"{__name__} - {self.__class__.__name__} - {self.name} has been closed with {status_code}: {close_msg}"
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
        operation_logger.info(
            f"{__name__} - {self.__class__.__name__} - {self.name}: Sent pong response to {ws.url}"
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
    """
    Binance Market WebSocket Client for public market data streams.
    Unlike UserWebSocketClient (request-response with polling), this uses
    the standard WebSocket push model:
    - Subscribe once → receive continuous push updates
    - Topic-based callbacks: callbacks[stream_name] (persistent)
    Stream format: "symbol@streamType" e.g., "btcusdt@ticker", "ethusdt@depth"
    """
    def __repr__(self):
        return f"BINANCE_{self.__class__.__name__}: {self.name}"

    def __init__(
        self,
        ping_interval: int | None = None,
        url: str = "wss://fstream.binance.com/ws",  # Market Stream
        default_callback: Callable | None = None,
        name: str = None,
    ) -> None:
        super().__init__(
            name=name or "Binance_Market_WebSocket_Client",
            url=url,
            api_key=None,  # No auth needed for public streams
            secret_key=None,
            ping_interval=ping_interval,
        )

        # Topic-based callbacks: {stream_name: callback} - persistent, not one-shot
        self.callbacks_lock: threading.Lock = threading.Lock()
        self.callbacks: dict[str | int, Callable] = dict()

        # Track subscriptions for resubscribe on reconnect
        self.subscriptions_lock: threading.Lock = threading.Lock()
        self.subscriptions: set[str] = set()  # Set of stream names

        self.default_callback: Callable | None = default_callback

        # Threading events
        self._thread_stop: threading.Event = threading.Event()
        self._thread_pause: threading.Event = threading.Event()
        self._connection_ready: threading.Event = threading.Event()
        self._intentional_close: threading.Event = threading.Event()

        # Lock for reconnection
        self._reconnect_lock: threading.Lock = threading.Lock()

        # Request ID counter for subscribe/unsubscribe commands
        self._request_id_lock: threading.Lock = threading.Lock()

        # WebSocketApp
        self.ws: websocket.WebSocketApp = self._construct_wsa()
        return

    def _is_connected(self) -> bool:
        try:
            if self.ws and self.ws.sock and self.ws.sock.connected:
                return True
        except Exception as e:
            operation_logger.critical(
                f"{__name__} - {self.__class__.__name__} - {self.name} - "
                f"Unexpected problem while checking the connection state: {str(e)}"
            )
        return False

    def start(self) -> None:
        self.connect()

    def send(self, data: dict) -> None:
        """Send a payload to the WebSocket server."""
        if isinstance(data, dict):
            payload = json.dumps(data)
            try:
                if self._is_connected():
                    self.ws.send(payload)
            except Exception as e:
                operation_logger.warning(
                    f"{__name__} - {self.__class__.__name__} - {self.name} - "
                    f"Unexpected error while sending: {str(e)}"
                )
        else:
            operation_logger.critical(
                f"{__name__} - {self.__class__.__name__} - {self.name} - "
                f"Data must be a dictionary, got {type(data)}"
            )
            raise TypeError(f"Data must be a dictionary, got {type(data)}")
        return

    '''
    ####################################################################################
    #                                    Threads                                       #
    ####################################################################################
    '''
    def _initialize_threads(self) -> None:
        """Initialize connection thread. No polling needed for push-based streams."""
        self.threads.append(
            threading.Thread(
                name=f"{self.name}_connection_thread",
                target=self.ws.run_forever,
                kwargs={'ping_interval': 0},  # Server sends pings, we respond
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
                time.sleep(1.0)
            except Exception as e:
                operation_logger.critical(
                    f"{__name__} - {self.__class__.__name__} - {self.name} - "
                    f"{thread.name} has not been started successfully: {str(e)}"
                )
                raise
        return

    def _clean_up_connections(self) -> None:
        operation_logger.info(
            f"{__name__} - {self.__class__.__name__} - {self.name} - "
            f"Cleaning up {len(self.threads)} threads."
        )

        self._thread_stop.set()

        try:
            if self._is_connected():
                self.ws.close()
            else:
                operation_logger.info(
                    f"{__name__} - {self.__class__.__name__} - {self.name} - "
                    f"No need to close the WebSocket since the WebSocket already closed."
                )
        except Exception as e:
            operation_logger.critical(
                f"{__name__} - {self.__class__.__name__} - {self.name} - "
                f"Unexpected error during close: {str(e)}"
            )

        self.threads.clear()
        self._thread_stop.clear()
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
        self._intentional_close.set()
        if self._is_connected():
            self.ws.close()
        return

    def subscribe(
        self,
        streams: str | list[str],
        push_topic: str | list[str],
        callback: Callable,
    ) -> None:
        """
        Subscribe to one or more market data streams.

        Args:
            streams: Stream name(s) e.g., "btcusdt@ticker" or ["btcusdt@ticker", "ethusdt@depth"]
            callback: Function to call when data arrives for these streams

        Binance format: {"method": "SUBSCRIBE", "params": ["stream1", "stream2"], "id": 1}
        """
        if not (isinstance(streams, str) and isinstance(push_topic, str) and isinstance(callback, Callable)):
            operation_logger.critical(
                f"{__name__} - {self.__class__.__name__} - {self.name} - "
                f"Parameter type error in subscribe(): 'streams' and 'push_topic' "
                f"must be strings, and 'callback' must be a Callable."
            )
            raise TypeError(
                f"{__name__} - {self.__class__.__name__} - {self.name} - "
                f"Parameter type error in subscribe(): 'streams' and 'push_topic' "
                f"must be strings, and 'callback' must be a Callable."
            )

        # Normalize to list
        if isinstance(streams, str):
            streams = [streams]

        # Register callbacks for each stream (persistent, not one-shot)
        with self.callbacks_lock:
            self.callbacks[push_topic] = callback

        # Track for resubscribe on reconnect
        with self.subscriptions_lock:
            self.subscriptions.update(streams)

        # Build and send subscribe request
        payload = {
            "method": "SUBSCRIBE",
            "params": streams,
            "id": self.generate_timestamp(),
        }

        self.send(payload)
        operation_logger.info(
            f"{__name__} - {self.__class__.__name__} - {self.name} - "
            f"Subscribed to streams: {streams}"
        )
        return

    def unsubscribe(
        self,
        streams: str | list[str],
    ) -> None:
        """
        Unsubscribe from one or more market data streams.
        Args:
            streams: Stream name(s) to unsubscribe from
        """
        # Normalize to list
        if isinstance(streams, str):
            streams = [streams]

        # Remove callbacks
        with self.callbacks_lock:
            for stream in streams:
                self.callbacks.pop(stream, None)

        # Remove from subscription tracking
        with self.subscriptions_lock:
            self.subscriptions.difference_update(streams)

        # Build and send unsubscribe request
        payload = {
            "method": "UNSUBSCRIBE",
            "params": streams,
            "id": self.generate_timestamp(),
        }

        self.send(payload)
        operation_logger.info(
            f"{__name__} - {self.__class__.__name__} - {self.name} - "
            f"Unsubscribed from streams: {streams}"
        )
        return

    def _resubscribe(self) -> None:
        """Resubscribe to all streams after reconnection."""
        with self.subscriptions_lock:
            if not self.subscriptions:
                return
            streams = list(self.subscriptions)

        payload = {
            "method": "SUBSCRIBE",
            "params": streams,
            "id": self.generate_timestamp(),
        }

        self.send(payload)
        operation_logger.info(
            f"{__name__} - {self.__class__.__name__} - {self.name} - "
            f"Resubscribed to {len(streams)} streams after reconnect."
        )
        return

    def _reconnect(self) -> None:
        """Handle reconnection with lock to prevent concurrent attempts."""
        if not self._reconnect_lock.acquire(blocking=False):
            operation_logger.info(
                f"{__name__} - {self.__class__.__name__} - {self.name} - "
                f"Reconnection already in progress, skipping."
            )
            return

        try:
            operation_logger.info(
                f"{__name__} - {self.__class__.__name__} - {self.name} - "
                f"Starting reconnection process..."
            )

            self._thread_stop.set()
            self._connection_ready.clear()

            self._clean_up_connections()

            # Rebuild WebSocketApp and reconnect
            self.ws = self._construct_wsa()
            self.connect()
        finally:
            self._reconnect_lock.release()
        return

    def _handle_reconnect(self, retry_delay: float = 3.0) -> None:
        """Handle reconnection in a separate thread with retry logic."""
        time.sleep(0.5)

        while True:
            if self._intentional_close.is_set():
                operation_logger.info(
                    f"{__name__} - {self.__class__.__name__} - {self.name} - "
                    f"Intentional close detected during reconnect, aborting."
                )
                return

            try:
                operation_logger.info(
                    f"{__name__} - {self.__class__.__name__} - {self.name} - "
                    f"Attempting reconnection..."
                )

                self._reconnect()

                # Wait for connection to be ready
                if self._connection_ready.wait(timeout=10.0):
                    self._resubscribe()
                    operation_logger.info(
                        f"{__name__} - {self.__class__.__name__} - {self.name} - "
                        f"Reconnection completed successfully."
                    )
                    return

            except Exception as e:
                operation_logger.warning(
                    f"{__name__} - {self.__class__.__name__} - {self.name} - "
                    f"Reconnection attempt failed: {str(e)}"
                )

            operation_logger.info(
                f"{__name__} - {self.__class__.__name__} - {self.name} - "
                f"Waiting {retry_delay}s before next reconnect attempt..."
            )
            time.sleep(retry_delay)
        return

    '''
    ####################################################################################
    #                           Overriden - WebSocketApp                               #
    ####################################################################################
    '''
    def on_open(self, ws: websocket.WebSocketApp) -> None:
        operation_logger.info(
            f"{__name__} - {self.__class__.__name__} - {self.name} - "
            f"WebSocket opened, connected to {ws.url} [v]"
        )
        return

    def on_message(
        self,
        ws: websocket.WebSocketApp,
        msg: str | bytes,
    ) -> None:
        """
        Handle incoming messages from market stream.

        Message formats:
        - Push data: {"e": "24hrTicker", "s": "BTCUSDT", ...} (raw stream)
        - Combined stream: {"stream": "btcusdt@ticker", "data": {...}}
        - Subscribe response: {"result": null, "id": 1}
        """
        if self._thread_pause.is_set():
            return

        # print(msg)

        try:
            data = json.loads(msg)
        except json.JSONDecodeError as e:
            operation_logger.warning(
                f"{__name__} - {self.__class__.__name__} - {self.name} - "
                f"Failed to parse message: {str(e)}"
            )
            return

        stream_topic: str = data.get("e")

        # Dispatch to registered callback
        with self.callbacks_lock:
            callback = self.callbacks.get(stream_topic)

        if callback:
            callback(data)
        elif self.default_callback:
            self.default_callback(data)
        else:
            self._operation_logging(data)
        return

    def on_close(
        self,
        ws: websocket.WebSocketApp,
        status_code: int,
        close_msg: str,
    ) -> None:
        operation_logger.warning(
            f"{__name__} - {self.__class__.__name__} - {self.name} - "
            f"WebSocket closed with {status_code}: {close_msg}"
        )

        if self._intentional_close.is_set():
            self._intentional_close.clear()
            return

        operation_logger.info(
            f"{__name__} - {self.__class__.__name__} - {self.name} - "
            f"Accidental closure detected, spawning reconnection thread."
        )

        reconnection_thread = threading.Thread(
            name=f"{self.name}_reconnection_thread",
            target=self._handle_reconnect,
            daemon=True,
        )
        reconnection_thread.start()
        return

    def on_error(self, ws: websocket.WebSocketApp, error: Exception) -> None:
        operation_logger.error(
            f"{__name__} - {self.__class__.__name__} - {self.name} - "
            f"WebSocket error: {str(error)}"
        )
        return

    def on_ping(self, ws: websocket.WebSocketApp, data: str | bytes) -> None:
        """Respond to server ping with pong."""
        ws.sock.pong(data)
        operation_logger.info(
            f"{__name__} - {self.__class__.__name__} - {self.name} - "
            f"Sent pong response to {ws.url}"
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
    ) -> websocket.WebSocketApp:
        def on_open_wrapper(ws: websocket.WebSocketApp):
            self._connection_ready.set()
            (on_open or self.on_open)(ws)
            return

        return websocket.WebSocketApp(
            url=self.url,
            on_open=on_open_wrapper,
            on_close=on_close or self.on_close,
            on_message=on_message or self.on_message,
            on_error=on_error or self.on_error,
            on_ping=self.on_ping,
        )


class TradingWebSocketClient(BasicWebSocketClient):
    def __init__(
        self,
        name: str,
        api_key: str,
        secret_key: str,
        ping_interval: int | None,
        url: str = "wss://ws-fapi.binance.com/ws-fapi/v1",  # Trade Stream
        default_callback: Callable | None = None,
    ) -> None:
        raise NotImplementedError
        return
