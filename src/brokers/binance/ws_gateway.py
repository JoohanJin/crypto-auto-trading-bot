# Standard Library
import base64
import json
import threading
import time
from collections.abc import Callable
from urllib.parse import urlencode

import websocket
from cryptography.hazmat.primitives.serialization import load_pem_private_key

from src.brokers.base.ws_service import WebSocket
from src.infrastructure.logging.set_logger import get_adapter, get_logger


logger = get_logger(__name__)


class BinanceUserWebSocket(WebSocket):
    def generate_method_id(self) -> int:
        return self.generate_timestamp()

    def __repr__(self):
        return f"BINANCE_USER_WEBSOCKET:{self.name}"

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
            name=name or "BINANCE_USER_WEBSOCKET_CLIENT",
            url=url,
            api_key=api_key,
            secret_key=secret_key,
            ping_interval=ping_interval,
        )
        self.logger = get_adapter(logger, f"{self.__class__.__name__}_{self.name}")

        self.private_key = None
        if secret_key:
            # Load from PEM content string
            self.private_key = load_pem_private_key(
                data=secret_key.encode("utf-8"), password=None
            )

        # callback function map based on the topics
        self.callbacks_lock: threading.Lock = threading.Lock()
        self.callbacks: dict[str | int, Callable] = {}

        self.subscriptions_lock: threading.Lock = threading.Lock()
        self.subscriptions: dict[int, dict] = {}  # {id: str | bytes} to be sent

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

    def _is_connected(self) -> bool:
        try:
            if self.ws and self.ws.sock and self.ws.sock.connected:
                return True
        except Exception as e:
            self.logger.critical(
                f"[WS_PING_PONG] Binance | Error: {type(e).__name__}: {e!s}"
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
                self.logger.info(
                    f"[WS_AUTH_ERROR] Binance | Error: {type(e).__name__}: {e!s}"
                )
        else:
            self.logger.critical(
                f"[BROKER_ERROR] Binance | Error: Data must be a dictionary, got {type(data)}"
            )
            raise

    def _authenticate(self) -> None:
        """
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
        """
        id: int = self.generate_timestamp()

        params = {
            "apiKey": self.api_key,
            "timestamp": id,
        }

        signature: str = self._generate_signature(params)

        params["signature"] = signature

        payload: dict = {
            "id": id,
            "method": "session.logon",
            "params": params,
        }

        with self.callbacks_lock:
            self.callbacks[id] = self._update_authenticated
        try:
            self.send(payload)
            time.sleep(1)
            return
        except Exception as e:
            self.logger.critical(
                f"[WS_AUTH_ERROR] Binance | Error: {type(e).__name__}: {e!s}"
            )
        return

    def _update_authenticated(self, data: dict | list) -> None:
        if isinstance(data, dict):
            if data.get("status", None) == 200:
                self._authenticated = True
                self.logger.info("[WS_AUTH_SUCCESS] Binance | Status: authenticated")
        else:
            self.logger.critical(
                "[WS_AUTH_ERROR] Binance | Error: Authentication msg format is wrong."
            )
            raise TypeError("authentication msg format is wrong.")

    def _generate_signature(
        self,
        params: dict,
    ) -> str:
        # sort params based on the key
        query_str: str = urlencode(sorted(params.items()))

        # Sign with Ed25519 private key and base64 encode
        signature = self.private_key.sign(query_str.encode("ASCII"))
        return base64.b64encode(signature).decode("ASCII")

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

    def _construct_params(self, params: dict) -> dict:
        # Remove old signature before regenerating (signature should not be part of signed payload)
        params.pop("signature", None)
        params["apiKey"] = self.api_key
        params["timestamp"] = self.generate_timestamp()
        params["signature"] = self._generate_signature(params)

    """
    #######################
    # Threads
    #######################
    """

    def _initialize_threads(self) -> None:
        self.threads.append(
            threading.Thread(
                name=f"{self.name}_connection_thread",
                target=self.ws.run_forever,
                kwargs={"ping_interval": 0},
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

        self.threads.append(
            threading.Thread(name="websocket_hb", target=self._heartbeat, daemon=True)
        )

    def _start_threads(self) -> None:
        for thread in self.threads:
            try:
                thread.start()
                self.logger.info(f"[THREAD_START] {thread.name} | Status: running")
                time.sleep(1.0)
            except Exception as e:
                self.logger.critical(
                    f"[THREAD_ERROR] {thread.name} failed | Error: {type(e).__name__}: {e!s}"
                )
                raise

    def _clean_up_connections(self) -> None:
        self.logger.info(f"[SHUTDOWN] Cleaning up {len(self.threads)} threads.")

        self._thread_stop.set()

        try:
            if self._is_connected():
                self.ws.close()
            else:
                self.logger.critical(
                    "[WS_CLOSE] Binance | Status: 0 | Reason: WebSocket already closed."
                )
        except Exception as e:
            self.logger.critical(
                f"[WS_CLOSE] Binance | Error: {type(e).__name__}: {e!s}"
            )

        self.threads.clear()
        self._thread_stop.clear()

    def _handle_reconnect(
        self,
        retry_delay: float = 3.0,
    ):
        # Give the old websocket_connection thread time to fully exit
        time.sleep(0.5)

        while not self._is_connected():
            if self._intentional_close.is_set():
                self.logger.info(
                    "[WS_CLOSE] Binance | Reason: Intentional close during reconnect"
                )
                return

            try:
                self.logger.info("[WS_RECONNECT] Binance | Attempt: retrying...")

                self._reconnect()

                # Wait for connection to be ready
                if self._connection_ready.wait(timeout=10.0):
                    self._resubscribe()
                    self.logger.info("[SUCCESS] Reconnection successful")
                    return

            except Exception as e:
                self.logger.warning(
                    f"[WS_RECONNECT] Binance | Error: {type(e).__name__}: {e!s}"
                )

            # Wait before next attempt
            self.logger.info(f"[WS_RECONNECT] Binance | Next Retry: {retry_delay:.2f}s")
            time.sleep(retry_delay)
        return

    # Override: previously ping method
    def _heartbeat(
        self,
    ) -> None:
        prev_timestamp: int = 0

        while not (self._thread_stop.is_set()) and (self._is_connected()):
            # self._thread_pause.wait()
            if self.generate_timestamp() - prev_timestamp > (
                self.ping_interval * 1_000
            ):
                try:
                    # ! WebSocketApp.send() requires str or bytes -> needs to dump it using json, i.e., json.dump(dict)
                    self.ws.sock.pong()
                    self.logger.debug(
                        "[WS_PING_PONG] Binance | Type: PONG | Status: success"
                    )
                    prev_timestamp = self.generate_timestamp()
                except Exception as e:
                    self.logger.warning(
                        f"[WS_PING_PONG] MexC | Error: {type(e).__name__}: {e!s}"
                    )
            else:
                continue

    """
    ####################################################################################
    #                                    Overriden                                     #
    ####################################################################################
    """

    def connect(self) -> None:
        self._initialize_threads()
        self._start_threads()

    def disconnect(self) -> None:
        if self._is_connected():
            self.ws.close()
            self._intentional_close.set()

    def subscribe(
        self,
        method: str,
        callback_function: Callable,
        params: dict | None = None,
    ) -> None:
        id: int = self.generate_method_id()

        if params is None:
            params = {}

        payload = {
            "id": id,
            "method": method,
            "params": params,
        }

        with self.callbacks_lock:
            self.callbacks[id] = callback_function

        with self.subscriptions_lock:
            self.subscriptions[id] = payload

    def unsubscribe(self) -> None:
        return

    def _resubscribe(self) -> None:
        return

    def _reconnect(self) -> None:
        # Prevent concurrent reconnection attempts
        if not self._reconnect_lock.acquire(blocking=False):
            self.logger.info(
                "[WS_RECONNECT] Binance | Reason: Reconnection already in progress"
            )
            return

        try:
            self.logger.info("[WS_RECONNECT] Binance | Status: Starting process")

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

    """
    ####################################################################################
    #                           Overriden - WebSocketApp                               #
    ####################################################################################
    """

    def on_open(
        self,
        ws: websocket.WebSocketApp,
    ) -> None:
        self.logger.info(f"[WS_OPEN] Binance | URL: {ws.url} | Status: opened")

    def on_message(
        self,
        ws: websocket.WebSocketApp,
        msg: str | bytes,
    ) -> None:
        data = json.loads(msg)
        method_id = data.get("id")

        if method_id and isinstance(method_id, int):
            with self.callbacks_lock:
                callback = self.callbacks.get(method_id, None)

            if isinstance(callback, Callable):
                callback(data)
            elif isinstance(self.default_callback, Callable):
                self.default_callback(data)
            else:
                self._operation_logging(data)

    def on_close(
        self,
        ws: websocket.WebSocketApp,
        status_code: int,
        close_msg: str,
    ) -> None:
        self.logger.warning(
            f"[WS_CLOSE] Binance | Status: {status_code} | Reason: {close_msg}"
        )

        if self._intentional_close.is_set():
            self._intentional_close.clear()
            return

        else:
            self.logger.info(
                "[WS_RECONNECT] Binance | Status: Accidental closure detected"
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
        self.logger.debug("[WS_PING_PONG] Binance | Type: PONG | Status: success")

    """
    ####################################################################################
    #                                    WebSocketApp                                  #
    ####################################################################################
    """

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

        return websocket.WebSocketApp(
            url=self.url,
            on_open=on_open_wrapper,
            on_close=on_close or self.on_close,
            on_message=on_message or self.on_message,
            on_error=on_error or self.on_error,
            on_ping=self.on_ping,
        )


class BinanceMarketWebSocket(WebSocket):
    """
    Binance Market WebSocket Client for public market data streams.
    Unlike UserWebSocket (request-response with polling), this uses
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
        self.logger = get_adapter(logger, f"{self.__class__.__name__}_{self.name}")

        # Topic-based callbacks: {stream_name: callback} - persistent, not one-shot
        self.callbacks_lock: threading.Lock = threading.Lock()
        self.callbacks: dict[str | int, Callable] = {}

        # Track subscriptions for resubscribe on reconnect
        self.subscriptions_lock: threading.Lock = threading.Lock()
        self.subscriptions: set[str] = set()  # Set of stream names

        # This is for acknowledgement of the subscriptions from Binance Broker
        self.streams_lock: threading.Lock = threading.Lock()
        self.streams: dict[int, str] = {}

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

    def _is_connected(self) -> bool:
        try:
            if self.ws and self.ws.sock and self.ws.sock.connected:
                return True
        except Exception as e:
            self.logger.critical(
                f"Unexpected problem while checking the connection state: {e!s}"
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
                self.logger.warning(f"Unexpected error while sending: {e!s}")
        else:
            self.logger.critical(f"Data must be a dictionary, got {type(data)}")
            raise TypeError(f"Data must be a dictionary, got {type(data)}")

    """
    ####################################################################################
    #                                    Threads                                       #
    ####################################################################################
    """

    def _initialize_threads(self) -> None:
        """Initialize connection thread. No polling needed for push-based streams."""
        self.threads.append(
            threading.Thread(
                name=f"{self.name}_connection_thread",
                target=self.ws.run_forever,
                kwargs={"ping_interval": 0},  # Server sends pings, we respond
                daemon=True,
            )
        )

    def _start_threads(self) -> None:
        for thread in self.threads:
            try:
                thread.start()
                self.logger.info(f"[THREAD_START] {thread.name} | Status: running")
                time.sleep(1.0)
            except Exception as e:
                self.logger.critical(
                    f"[THREAD_ERROR] {thread.name} failed | Error: {type(e).__name__}: {e!s}"
                )
                raise

    def _clean_up_connections(self) -> None:
        self.logger.info(f"[SHUTDOWN] Cleaning up {len(self.threads)} threads.")

        self._thread_stop.set()

        try:
            if self._is_connected():
                self.ws.close()
            else:
                self.logger.info(
                    "[WS_CLOSE] Binance | Reason: WebSocket already closed."
                )
        except Exception as e:
            self.logger.critical(
                f"[WS_CLOSE] Binance | Error: {type(e).__name__}: {e!s}"
            )

        self.threads.clear()
        self._thread_stop.clear()

    """
    ####################################################################################
    #                                    Overriden                                     #
    ####################################################################################
    """

    def connect(self) -> None:
        self._initialize_threads()
        self._start_threads()

    def disconnect(self) -> None:
        self._intentional_close.set()
        if self._is_connected():
            self.ws.close()

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
        if not (
            isinstance(streams, str)
            and isinstance(push_topic, str)
            and isinstance(callback, Callable)
        ):
            self.logger.critical(
                "Parameter type error in subscribe(): 'streams' and 'push_topic' "
                "must be strings, and 'callback' must be a Callable."
            )
            raise TypeError(
                f"{__name__} - {self.__class__.__name__} - {self.name} - "
                f"Parameter type error in subscribe(): 'streams' and 'push_topic' "
                f"must be strings, and 'callback' must be a Callable."
            )

        id: int = self.generate_timestamp()

        # Normalize to list
        if isinstance(streams, str):
            streams = [streams]

        # Build and send subscribe request
        payload = {
            "method": "SUBSCRIBE",
            "params": streams,
            "id": id,
        }

        # Register callbacks for each stream (persistent, not one-shot)
        try:
            self.send(payload)
            self.logger.info(
                f"[WS_SUBSCRIBE] Binance | Topic: {streams} | Status: sent"
            )

            with self.callbacks_lock:
                self.callbacks[push_topic] = callback

            # Track for resubscribe on reconnect
            with self.subscriptions_lock:
                self.subscriptions.update(streams)

            # for acknowledgement
            with self.streams_lock:
                self.streams[id] = streams
        except Exception as e:
            self.logger.warning(
                f"[WS_SUBSCRIBE] Binance | Error: {type(e).__name__}: {e!s}"
            )

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
        self.logger.info(
            f"[WS_UNSUBSCRIBE] Binance | Topic: {streams} | Status: unsubscribed"
        )

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
        self.logger.info(f"Resubscribed to {len(streams)} streams after reconnect.")
        return

    def _reconnect(self) -> None:
        """Handle reconnection with lock to prevent concurrent attempts."""
        if not self._reconnect_lock.acquire(blocking=False):
            self.logger.info("Reconnection already in progress, skipping.")
            return

        try:
            self.logger.info("Starting reconnection process...")

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
                self.logger.info(
                    "Intentional close detected during reconnect, aborting."
                )
                return

            try:
                self.logger.info("Attempting reconnection...")

                self._reconnect()

                # Wait for connection to be ready
                if self._connection_ready.wait(timeout=10.0):
                    self._resubscribe()
                    self.logger.info("Reconnection completed successfully.")
                    return

            except Exception as e:
                self.logger.warning(f"Reconnection attempt failed: {e!s}")

            self.logger.info(f"Waiting {retry_delay}s before next reconnect attempt...")
            time.sleep(retry_delay)
        return

    """
    ####################################################################################
    #                           Overriden - WebSocketApp                               #
    ####################################################################################
    """

    def on_open(self, ws: websocket.WebSocketApp) -> None:
        self.logger.info(f"[WS_OPEN] Binance | URL: {ws.url} | Status: opened")

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

        try:
            msg: dict = json.loads(msg)
            if isinstance(msg, dict):
                self._deal_with_response(msg)
        except json.JSONDecodeError as e:
            self.logger.warning(f"Failed to parse message: {e!s}")
            return
        except Exception as e:
            self.logger.warning(
                f"Unexpected while getting msg from Binance WebSocket API: {e!s}"
            )
        return

    def _deal_with_response(
        self,
        msg: dict,
    ) -> None:
        # subscription acknowledgement
        def is_sub_response(msg):
            # {'result': None, 'id': 1770044294399}
            id: int = msg.get("id", -1)
            stream: str = self.streams.get(id, None)

            if stream is not None:
                self.logger.info(
                    f"[WS_SUBSCRIBE] Binance | Topic: {stream} | Status: subscribed"
                )

        def deal_with_msg(msg):
            stream_topic: str = msg.get("e")

            # Dispatch to registered callback
            with self.callbacks_lock:
                callback = self.callbacks.get(stream_topic)

            if isinstance(callback, Callable):
                callback(msg)
            elif self.default_callback:
                self.default_callback(msg)

        if msg.get("result", "") is None:
            is_sub_response(msg)
        else:
            deal_with_msg(msg)

    def on_close(
        self,
        ws: websocket.WebSocketApp,
        status_code: int,
        close_msg: str,
    ) -> None:
        self.logger.warning(
            f"[WS_CLOSE] Binance | Status: {status_code} | Reason: {close_msg}"
        )

        if self._intentional_close.is_set():
            self._intentional_close.clear()
            return

        self.logger.info("[WS_RECONNECT] Binance | Status: Accidental closure detected")

        reconnection_thread = threading.Thread(
            name=f"{self.name}_reconnection_thread",
            target=self._handle_reconnect,
            daemon=True,
        )
        reconnection_thread.start()
        return

    def on_error(self, ws: websocket.WebSocketApp, error: Exception) -> None:
        self.logger.error(
            f"[WS_PING_PONG] Binance | Error: {type(error).__name__}: {error!s}"
        )

    def on_ping(self, ws: websocket.WebSocketApp, data: str | bytes) -> None:
        """Respond to server ping with pong."""
        ws.sock.pong(data)
        self.logger.debug("[WS_PING_PONG] Binance | Type: PONG | Status: success")

    """
    ####################################################################################
    #                                    WebSocketApp                                  #
    ####################################################################################
    """

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

        return websocket.WebSocketApp(
            url=self.url,
            on_open=on_open_wrapper,
            on_close=on_close or self.on_close,
            on_message=on_message or self.on_message,
            on_error=on_error or self.on_error,
            on_ping=self.on_ping,
        )


class BinanceTradingWebSocket(WebSocket):
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
