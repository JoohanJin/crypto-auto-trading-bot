# Built-in Library
import hashlib
import hmac
import json
import threading
import time
from typing import Callable

import websocket

# Custom Library
from src.brokers.base.ws_service import WebSocket
# Getting Logger access
from src.infrastructure.logging.set_logger import get_adapter, get_logger

logger = get_logger(__name__)


class MexcWebSocket(WebSocket):
    '''
    mexc websocket
    payload = {
        "method": "sub.tickers",
        "param": {}
    }
    '''

    def __init__(
        self,
        url: str,   # = "wss://contract.mexc.com/edge",
        name: str,
        api_key: str,
        secret_key: str,
        ping_interval: int,
        default_callback: Callable | None = None,
    ) -> None:
        super().__init__(
            url=url,
            name=name or f"MEXC_WEBSOCKET_CLIENT_{self.id}",
            api_key=api_key,
            secret_key=secret_key,
            ping_interval=ping_interval,
        )
        self.logger = get_adapter(logger, self.name)

        # internal DataStructure
        self.default_callback: Callable = default_callback
        self.authenticated: bool = False

        # subscriptions fetching for resubscriptiong
        self.subscriptions: list[str] = []

        # callback function map based on the topics
        self.callbacks: dict[str | int, Callable] = {}

        # Thread Events
        self._thread_stop: threading.Event = threading.Event()
        self._thread_pause: threading.Event = threading.Event()
        self._connection_ready: threading.Event = threading.Event()
        self._intentional_close: threading.Event = threading.Event()  # Track intentional disconnects

        self._reconnect_lock: threading.Lock = threading.Lock()  # Prevent concurrent reconnects

        self.ws: websocket.WebSocketApp | None = self._construct_websocket()
        return

    def start(self,) -> None:
        self.connect()
        return

    def pause(self,) -> None:
        self._thread_pause.set()
        return

    def resume(self) -> None:
        self._thread_pause.clear()
        return

    # Override
    def connect(self) -> None:
        # WebSocketApp-related
        if ((self.ws is None) or (self.ws.sock is None)):
            self.ws = self._construct_websocket()

        # Threads-related
        # Clear existing thread references before re-initializing
        self.threads = [t for t in self.threads if t.is_alive() and t.name != "websocket_hb"]

        self._initialize_threads()
        self._start_threads()
        return

    # Override
    def disconnect(self) -> None:
        self._intentional_close.set()  # Mark as intentional before closing
        if self._is_connected():
            self.ws.close()
        return

    # Override
    def subscribe(
        self,
        topic: str,
        callback: Callable,
        param: dict | None = None,
    ) -> None:
        if param is None:
            param: dict = {}

        self._push_callback_func(topic, callback)

        if not topic.startswith("sub."):
            topic = "sub." + topic

        while not self._is_connected():
            time.sleep(0.1)

        header = json.dumps({
            "method": topic,
            "param": param,
        })

        try:
            self.send(header)
            self.subscriptions.append(header)
            self.logger.info(f"[WS_SUBSCRIBE] MexC | Topic: {topic} | Status: sent")
        except Exception as e:
            self.logger.warning(f"[WS_SUBSCRIBE] MexC | Error: {type(e).__name__}: {str(e)}")
            self._pop_callback_func(topic=topic)
        return

    # Override
    def unsubscribe(self, topic: str) -> None:
        if self.callbacks.get(topic, None):
            del self.callbacks[topic]

        if topic.startswith("unsub."):
            topic = "unsub." + topic

        self.send(
            json.dumps({
                "method": topic,
                "param": {},
            })
        )
        self.logger.info(f"[WS_UNSUBSCRIBE] MexC | Topic: {topic} | Status: unsubscribed")
        return

    def _construct_websocket(
        self,
        url: str | None = None,
        on_open: Callable | None = None,
        on_message: Callable | None = None,
        on_close: Callable | None = None,
        on_error: Callable | None = None,
        on_ping: Callable | None = None
    ) -> websocket.WebSocketApp:
        def on_open_wrapper(ws: websocket.WebSocketApp):
            self._connection_ready.set()

            (on_open or self.on_open)(ws)
            return

        try:
            ws = websocket.WebSocketApp(
                url=url or self.url,
                on_message=on_message or self.on_message,
                on_open=on_open_wrapper,
                on_close=on_close or self.on_close,
                on_error=on_error or self.on_error,
                on_ping=on_ping or self.on_ping,
            )
            time.sleep(0.5)

            return ws
        except Exception as e:
            self.logger.error(f"Failed to construct websocket object: {str(e)}")
            raise

    def _initialize_threads(self) -> None:
        ws_connection: threading.Thread = threading.Thread(
            name="websocket_connection",
            target=self.ws.run_forever,
            kwargs={'ping_interval': 0},
            daemon=True,
        )
        ws_hm: threading.Thread = threading.Thread(
            name="websocket_hb",
            target=self._heartbeat,
            daemon=True
        )

        self.threads.extend([ws_connection, ws_hm])
        return

    def _start_threads(self) -> None:
        for thread in self.threads:
            try:
                thread.start()
                self.logger.info(f"[THREAD_START] {thread.name} | Status: running")
                time.sleep(0.5)
            except Exception as e:
                self.logger.critical(f"[THREAD_ERROR] {thread.name} failed | Error: {type(e).__name__}: {str(e)}")
                raise
        return

    def _pause_threads(self) -> None:
        self._thread_pause.set()
        return

    def _clean_up_connections(self) -> None:
        '''
        Join and remove all threads from self.threads container
        '''
        self.logger.info(f"[SHUTDOWN] Cleaning up {len(self.threads)} threads.")

        self._thread_stop.set()  # Set it to the True to stop threads

        # Only try to close if socket exists and is actually connected
        try:
            if self._is_connected():
                self.logger.info("[WS_CLOSE] MexC | Reason: cleanup")
                self.ws.close()  # force the run_forever function to return.
        except Exception as e:
            self.logger.warning(f"[WS_CLOSE] MexC | Error: {type(e).__name__}: {str(e)}")

        # Get current thread to avoid self-join deadlock
        current_thread: threading.Thread = threading.current_thread()

        for thread in self.threads:
            # skip if it is the current thread
            if thread is current_thread:
                self.logger.info(f"[SHUTDOWN] Skipping current thread ({thread.name}).")
                continue

            if thread.is_alive():
                self.logger.info(f"[SHUTDOWN] Waiting for {thread.name} to finish...")
                thread.join(timeout=2.0)

                while (thread.is_alive()):
                    self.logger.warning(
                        (
                            f"[THREAD_ERROR] {thread.name} did not stop cleanly. "
                            f"waiting for {thread.name} to be terminated properly."
                        )
                    )
                    thread.join(timeout=2.0)
                else:
                    self.logger.info(f"[SHUTDOWN] {thread.name} stopped successfully.")
            else:
                self.logger.info(f"[SHUTDOWN] {thread.name} already stopped successfully.")

        # remove all threads from list
        self.threads.clear()
        self._thread_stop.clear()
        self.ws = None
        self.logger.info("[SHUTDOWN] All threads cleaned up and removed.")
        return

    def _push_callback_func(
        self,
        topic: str,
        callback_func: Callable,
    ) -> None:
        # just overwrite no matter what
        self.callbacks[topic.replace("sub.", "").replace("push.", "")] = callback_func
        return

    def _pop_callback_func(
        self,
        topic: str,
    ) -> None:
        processed_topic: str = topic.replace("sub.").replace("push.")
        if (self.callbacks.get(processed_topic, None) is not None):
            del self.callbacks[processed_topic]
        return

    # Override
    def send(self, msg: str | bytes) -> None:
        if isinstance(msg, str) or isinstance(msg, bytes):
            self.ws.send(msg)
        else:
            self.logger.warning("The message to be sent by WebSocketApp should str or bytes.")
            raise ValueError()
        return

    # Override
    def _reconnect(self) -> None:
        # Prevent concurrent reconnection attempts
        if not self._reconnect_lock.acquire(blocking=False):
            self.logger.info("[WS_RECONNECT] MexC | Reason: Reconnection already in progress")
            return

        try:
            self.logger.info("[WS_RECONNECT] MexC | Status: Starting process")

            # Reset state - old threads will exit naturally when websocket closed
            self._thread_stop.clear()  # Clear stop signal for new threads
            self._connection_ready.clear()
            self.threads.clear()  # Clear old thread references (they've already exited)
            self.ws = None  # Clear old websocket reference

            # Reconnect with fresh websocket and threads
            self.connect()
        finally:
            self._reconnect_lock.release()
        return

    # Override: previously ping method
    def _heartbeat(
        self,
        hb_payload: str = '{"method":"ping"}',
    ) -> None:
        prev_timestamp: int = 0

        while not self._thread_stop.is_set():
            if self._thread_pause.is_set():
                time.sleep(1)
                continue

            if self._is_connected():
                if (self.generate_timestamp() - prev_timestamp > (self.ping_interval * 1_000)):
                    try:
                        self.send(hb_payload)
                        self.logger.debug("[WS_PING_PONG] MexC | Type: PING | Status: success")
                        prev_timestamp = self.generate_timestamp()
                    except Exception as e:
                        self.logger.warning(f"[WS_PING_PONG] MexC | Error: {type(e).__name__}: {str(e)}")

            time.sleep(1)  # Check every second to prevent high CPU usage
        return

    # Override
    def on_message(
        self,
        ws: websocket.WebSocketApp,
        msg: str | bytes,
    ) -> None:
        if self._thread_pause.is_set():
            return  # ignore all the data from websocket

        try:
            data: dict | list = None
            if isinstance(msg, str):
                data = json.loads(msg)
            if isinstance(msg, bytes):
                data = json.loads(msg.decode("utf-8"))

            if isinstance(data, dict):
                self._deal_with_response(data)
        except Exception as e:
            self.logger.warning(f"[BROKER_ERROR] MexC | Error: Failed to get the msg from the websocket: {str(e)}")
        return

    # Override
    def on_open(
        self,
        ws: websocket.WebSocketApp,
    ) -> None:
        self.logger.info(f"[WS_OPEN] MexC | URL: {self.url} | Status: opened")
        return

    # Override
    def on_close(
        self,
        ws: websocket.WebSocketApp,
        status_code: int,
        close_msg: str,
    ) -> None:
        self.logger.warning(f"[WS_CLOSE] MexC | Status: {status_code} | Reason: {close_msg}")

        # Check if this was an intentional close
        if self._intentional_close.is_set():
            self.logger.info("[WS_CLOSE] MexC | Reason: Intentional close")
            self._intentional_close.clear()  # Reset the flag
            return

        # Only reconnect for accidental closes
        # Status 1000 = normal closure, 1006 = abnormal closure (no close frame), None = network issue
        else:
            self.logger.info("[WS_RECONNECT] MexC | Status: Accidental closure detected")
            # Spawn a separate thread for reconnection to avoid deadlock
            # (on_close runs inside the websocket_connection thread)
            reconnect_thread = threading.Thread(
                name="websocket_reconnect",
                target=self._handle_reconnect,
                daemon=True,
            )
            reconnect_thread.start()
        return

    def _handle_reconnect(
        self,
        retry_delay: float = 3.0,
    ) -> None:
        """
        Handle reconnection in a separate thread to avoid deadlock.
        Called from on_close which runs inside the websocket_connection thread.

        Keeps trying until connection is established.
        """
        # Give the old websocket_connection thread time to fully exit
        time.sleep(0.5)

        while True:
            # Check if intentional close happened during retry
            if self._intentional_close.is_set():
                self.logger.info("[WS_CLOSE] MexC | Reason: Intentional close during reconnect")
                return

            try:
                self.logger.info("[WS_RECONNECT] MexC | Attempt: retrying...")

                self._reconnect()

                # Wait for connection to be ready
                if self._connection_ready.wait(timeout=10.0):
                    self._resubscribe()
                    self.logger.info("[SUCCESS] Reconnection completed successfully")
                    return  # Success!

            except Exception as e:
                self.logger.warning(f"[WS_RECONNECT] MexC | Error: {type(e).__name__}: {str(e)}")

            # Wait before next attempt
            self.logger.info(f"[WS_RECONNECT] MexC | Next Retry: {retry_delay:.2f}s")
            time.sleep(retry_delay)
        return

    # Override
    def on_error(
        self,
        ws: websocket.WebSocketApp,
        error: Exception,
    ) -> None:
        self.logger.error(f"[WS_PING_PONG] MexC | Error: {type(error).__name__}: {str(error)}")

        return

    # Override
    def on_ping(
        self,
        ws: websocket.WebSocketApp,
        data: bytes,
    ) -> None:
        # Standard MEXC pong response
        payload: str = json.dumps({"method": "pong"})
        try:
            ws.send(payload)
            self.logger.debug("[WS_PING_PONG] MexC | Type: PONG | Status: success")
        except Exception as e:
            self.logger.warning(f"[WS_PING_PONG] MexC | Error sending PONG: {str(e)}")
        return

    def authenticate(self) -> None:
        '''
        ;func authenticate():
            - authenticate the WebSocket connection to the private endpoint.

        ;param self:
            - the instance of the class

        ;return None
        '''
        timestamp: str = str(self.generate_timestamp())

        # hmac using sha256
        signature = self._generate_signature(timestamp)

        header = json.dumps({
            "subscribe": False,
            "method": "login",
            "param": {
                "apiKey": self.api_key,
                "reqTime": timestamp,
                "signature": signature,
            }
        })

        self.send(header)
        return None

    def _generate_signature(
        self,
        timestamp: str | None,
    ) -> str:
        if (timestamp is None):
            timestamp = str(self.generate_timestamp())

        if (self.api_key and self.secret_key):
            query_str = f"{self.api_key}{timestamp}"

            return hmac.new(
                self.secret_key.encode("utf-8"),
                query_str.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()

        return None

    def _deal_with_response(
        self,
        msg: dict,
    ):
        # comprehensive callback function which can deal with all of the message
        """
        ;func _deal_with
        ;Types of Response
            - auth_message
            - subscribe response
            - pong
        # Message Classification Sub-Functions
        """
        # Authententication ack or nack
        def is_auth_response(msg):
            if msg.get("channel") == "rs.login":
                return True
            return False

        # SUbscription ack or nack
        def is_sub_response(msg):
            if str(msg.get("channel", "")).startswith("rs.sub."):
                return True
            return False

        # ping-pong for connection maintainining
        def is_pong_msg(msg):
            if msg.get("channel", "") == "pong":
                return True
            return False

        # error message
        def is_error_msg(msg):
            if msg.get("channel", "") == "rs.error":
                return True
            return False
        '''
        # End of Message Classification Sub-Function.
        '''

        '''
        # Message Handling Sub-Functions
        '''
        def deal_with_auth_msg(msg):
            if (msg.get("data") == "success"):
                self.logger.info("[WS_AUTH_SUCCESS] MexC | Status: authenticated")
                self.authenticated = True
            else:
                self.logger.info("[WS_AUTH_ERROR] MexC | Status: failed")
                self.authenticated = False  # overwrite
            return

        def deal_with_sub_msg(
            msg: dict,
        ):
            topic = msg.get("channel")
            if (
                (
                    msg.get("channel", "").startswith("rs.")
                    or msg.get("channel", "").startswith("push.")
                )
                and (msg.get("channel", "") != "rs.error")
            ):
                self.logger.info(f"[WS_SUBSCRIBE] MexC | Topic: {topic} | Status: subscribed")
            else:
                self.logger.warning(f"[WS_SUBSCRIBE] MexC | Topic: {topic} | Status: failed")
            return

        def deal_with_msg(topic):
            # Change this to make it to the DTOs
            callback_function = self._get_callback_func(topic)

            if isinstance(callback_function, Callable):
                callback_function(msg)

            return
        '''
        # END of Message Handling Sub-Functions
        '''

        topic = msg.get("channel").replace("push.", "").replace("sub.", "")

        if is_auth_response(msg):
            deal_with_auth_msg(msg)

        elif is_sub_response(msg):
            deal_with_sub_msg(msg)

        elif is_error_msg(msg):
            self.logger.info(f"func _deal_with_response(): The error has been received from the host: {msg}")

        elif is_pong_msg(msg):  # Do Nothing
            pass

        else:
            deal_with_msg(topic)
        return

    def _get_callback_func(self, topic) -> Callable | None:
        return self.callbacks.get(topic, None)

    def _is_connected(self):
        try:
            return self.ws and self.ws.sock and self.ws.sock.connected
        except AttributeError:
            return False

    def _resubscribe(self) -> None:
        for subscription in self.subscriptions:
            self.send(subscription)
