# Built-in Library
import hashlib
import hmac
import json
import time
from typing import Callable
import threading
import websocket

# Custom Library
from service.sdk.websocket_sdk import BasicWebSocketClient

# Getting Logger access
from logger.set_logger import operation_logger


class FutureWebSocket(BasicWebSocketClient):
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
            url = url,
            name = name or f"MexC_WebSocket_Client_{self.id}",
            api_key = api_key,
            secret_key = secret_key,
            ping_interval = ping_interval,
        )

        # internal DataStructure
        self.default_callback: Callable = default_callback
        self.authenticated: bool = False

        # subscriptions fetching for resubscription
        self.subscriptions: list[str] = list()

        # callback function map based on the topics
        self.callbacks: dict[str | int, Callable] = dict()

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

    # Override
    def connect(self) -> None:
        # WebSocketApp-related
        if ((self.ws is None) or (self.ws.sock is None)):
            self.ws = self._construct_websocket()

        # Threads-related
        self._initialize_threads()

        self._start_threads()
        return

    # Override
    def disconnect(self) -> None:
        self._intentional_close.set()  # Mark as intentional before closing
        if self._is_connected():
            self.ws.close()
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
            operation_logger.error(
                f"{__name__} - {self.__class__.__name__} - Failed to construct websocket object: {str(e)}"
            )
            raise

    def pause(self,) -> None:
        self._thread_pause.set()
        return

    def resume(self) -> None:
        self._thread_pause.clear()
        return

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
                operation_logger.info(
                    f"{__name__} - {self.__class__.__name__} - Started thread: {thread.name}"
                )
                time.sleep(0.5)
            except Exception as e:
                operation_logger.critical(
                    f"{__name__} - {self.__class__.__name__} - Failed to start thread {thread.name}: {str(e)}"
                )
                raise
        return

    def _pause_threads(self) -> None:
        self._thread_pause.set()
        return

    def _clean_up_connections(self) -> None:
        '''
        Join and remove all threads from self.threads container
        '''
        operation_logger.info(
            f"{__name__} - {self.__class__.__name__} - Cleaning up {len(self.threads)} threads."
        )

        self._thread_stop.set()  # Set it to the True to stop threads

        # Only try to close if socket exists and is actually connected
        try:
            if self._is_connected():
                operation_logger.info("Closing Websocket to unblock run_forever...")
                self.ws.close()  # force the run_forever function to return.
        except Exception as e:
            operation_logger.warning(
                f"{__name__} - {self.__class__.__name__} - Socket already closed or error during close: {str(e)}"
            )

        # Get current thread to avoid self-join deadlock
        current_thread: threading.Thread = threading.current_thread()

        for thread in self.threads:
            # skip if it is the current thread
            if thread is current_thread:
                operation_logger.info(
                    f"{__name__} - {self.__class__.__name__} - Skipping current thread ({thread.name})."
                )
                continue

            if thread.is_alive():
                operation_logger.info(
                    f"{__name__} - {self.__class__.__name__} - Waiting for {thread.name} to finish..."
                )
                thread.join(timeout=2.0)

                while (thread.is_alive()):
                    operation_logger.warning(
                        (
                            f"{__name__} - {self.__class__.__name__} - {thread.name} did not stop cleanly. "
                            f"waiting for {thread.name} to be terminated properly."
                        )
                    )
                    thread.join(timeout=2.0)
                else:
                    operation_logger.info(
                        f"{__name__} - {self.__class__.__name__} - {thread.name} stopped successfully."
                    )
            else:
                operation_logger.info(
                    f"{__name__} - {self.__class__.__name__} - {thread.name} already stopped successfully."
                )

        # remove all threads from list
        self.threads.clear()
        self._thread_stop.clear()
        self.ws = None
        operation_logger.info(
            f"{__name__} - {self.__class__.__name__} - All threads cleaned up and removed."
        )
        return

    # Override
    def subscribe(
        self,
        topic: str,
        callback_function: Callable,
        param: dict | None = None,
    ) -> None:
        if param is None:
            param: dict = dict()

        self._push_callback_func(topic, callback_function)

        if not topic.startswith("sub."):
            topic = "sub." + topic

        while not self._is_connected():
            time.sleep(0.1)

        header = json.dumps(
            dict(
                method = topic,
                param = param,
            )
        )

        try:
            self.send(header)
            self.subscriptions.append(header)
        except Exception as e:
            operation_logger.warning(
                f"{__name__} - {self.__class__.__name__} - Unexpected error during subscription: {str(e)}"
            )
            self._pop_callback_func(topic=topic)
        return

    def _push_callback_func(
        self,
        topic: str,
        callback_func: Callable,
    ) -> None:
        # just overwrite no matter what
        self.callbacks[topic.replace("sub.", "").replace("push.", "")] = callback_func
        return

    # Override
    def unsubscribe(self, topic: str) -> None:
        if self.callbacks.get(topic, None):
            del self.callbacks[topic]

        if topic.startswith("unsub."):
            topic = "unsub." + topic

        self.send(
            json.dumps(
                dict(
                    method = topic,
                    param = dict(),
                )
            )
        )
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
            operation_logger.warning(
                f"{__name__} - {self.__class__.__name__} - The message to be sent by WebSocketApp should str or bytes."
            )
            raise ValueError()
        return

    # Override
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

    # Override: previously ping method
    def _heartbeat(
        self,
        hb_payload: str = '{"method":"ping"}',
    ) -> None:
        prev_timestamp: int = 0

        while (not (self._thread_stop.is_set()) and (self._is_connected())):
            # self._thread_pause.wait()
            if (self.generate_timestamp() - prev_timestamp > (self.ping_interval * 1_000)):
                try:
                    # ! websocket.send() requires str or bytes -> needs to dump it using json, i.e., json.dump(dict)
                    self.send(hb_payload)
                    operation_logger.info(
                        f"{__name__} - {self.__class__.__name__} - Successfully sent a ping message to {self.ws.url}"
                    )
                    prev_timestamp = self.generate_timestamp()
                except Exception as e:
                    operation_logger.warning(
                        f"{__name__} - {self.__class__.__name__} - Failed to send ping message: {str(e)}"
                    )
            else:
                continue
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
            if isinstance(msg, str):
                data: dict = json.loads(msg)
            if isinstance(msg, bytes):
                data: dict = json.loads(msg.decode("utf-8"))

            if isinstance(data, dict):
                self._deal_with_response(data)
        except Exception as e:
            operation_logger.warning(
                f"{__name__} - {self.__class__.__name__} - Failed to get the msg from the websocket: {str(e)}"
            )
        return

    # Override
    def on_open(
        self,
        ws: websocket.WebSocketApp,
    ) -> None:
        operation_logger.info(
            f"{__name__} - {self.__class__.__name__} - WebSocket has been opened and made a connection to {self.url}"
        )
        return

    # Override
    def on_close(
        self,
        ws: websocket.WebSocketApp,
        status_code: int,
        close_msg: str,
    ) -> None:
        operation_logger.warning(
            f"{__name__} - {self.__class__.__name__} - MexC WebSocket has been closed with {status_code}: {close_msg}"
        )

        # Check if this was an intentional close
        if self._intentional_close.is_set():
            operation_logger.info(
                f"{__name__} - {self.__class__.__name__} - MexC WebSocket - Intentional close detected, not reconnecting."
            )
            self._intentional_close.clear()  # Reset the flag
            return

        # Only reconnect for accidental closes
        # Status 1000 = normal closure, 1006 = abnormal closure (no close frame), None = network issue
        else:
            operation_logger.info(
                f"{__name__} - {self.__class__.__name__} - MexC WebSocket - Accidental MexC WebSocket close detected, spawning reconnection thread."
            )
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
                operation_logger.info(
                    f"{__name__} - {self.__class__.__name__} - MexC WebSocket - "
                    f"Intentional close detected during reconnect, aborting."
                )
                return

            try:
                operation_logger.info(
                    f"{__name__} - {self.__class__.__name__} - MexC WebSocket - Attempting reconnection..."
                )

                self._reconnect()

                # Wait for connection to be ready
                if self._connection_ready.wait(timeout=10.0):
                    self._resubscribe()
                    operation_logger.info(
                        f"{__name__} - {self.__class__.__name__} - MexC WebSocket - Reconnection completed successfully."
                    )
                    return  # Success!

            except Exception as e:
                operation_logger.warning(
                    f"{__name__} - {self.__class__.__name__} - MexC WebSocket - Reconnection attempt failed: {str(e)}"
                )

            # Wait before next attempt
            operation_logger.info(
                f"{__name__} - {self.__class__.__name__} - MexC WebSocket - "
                "Waiting {retry_delay}s before next reconnect attempt..."
            )
            time.sleep(retry_delay)
        return

    # Override
    def on_error(
        self,
        ws: websocket.WebSocketApp,
        error: Exception,
    ) -> None:
        operation_logger.error(
            f"{__name__} - {self.__class__.__name__} - WebSocket API: Unexpected Error Occured: {str(error)}."
        )

        return

    # Override
    def on_ping(
        self,
        ws: websocket.WebSocketApp,
        data: bytes,
    ) -> None:
        # need to send pong -> let's see what I can do with this on mexc.
        payload: str = "{'method':'pong'}"
        if isinstance(data, bytes):
            data = data.encode("utf-8")
            if (data.get("channel", "") == 'ping' or data.get('method', "") == 'ping'):
                ws.send(payload)
        else:
            return
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

        header = json.dumps(
            dict(
                subscribe=False,
                method="login",
                param=dict(
                    apiKey=self.api_key,
                    reqTime=timestamp,
                    signature=signature,
                )
            )
        )

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
                operation_logger.info(
                    f"{__name__} - {self.__class__.__name__} - Auth for {self.name} has been successful."
                )
                self.authenticated = True
            else:
                operation_logger.info(
                    f"{__name__} - {self.__class__.__name__} - Auth for {self.name} has failed."
                )
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
                operation_logger.info(
                    f"{__name__} - {self.__class__.__name__} - Subscription to {topic} has been established: [v]"
                )
            else:
                operation_logger.warning(
                    f"{__name__} - {self.__class__.__name__} - Subscription to {topic} has NOT been establish: [x]"
                )
            return

        def deal_with_msg(topic):
            callback_function = self._get_callback_func(topic)

            if isinstance(callback_function, Callable):
                callback_function(msg)
            return
        '''
        # END of Message Handling Sub-Functions
        '''

        # print(msg)
        topic = msg.get("channel").replace("push.", "").replace("sub.", "")

        if is_auth_response(msg):
            deal_with_auth_msg(msg)

        elif is_sub_response(msg):
            deal_with_sub_msg(msg)

        elif is_error_msg(msg):
            operation_logger.info(
                f"{__name__} - func _deal_with_response(): The error has been received from the host: {msg}"
            )

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
