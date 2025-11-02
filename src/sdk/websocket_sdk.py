# Built-in Library
import sys
from abc import ABC, abstractmethod
from typing import Optional, Callable
import time
import websocket
import json
import threading
import hmac
import hashlib

# Get the logger
from logger.set_logger import operation_logger


class BasicWebSocketManager(ABC):
    '''
    # Static Method
    '''
    @staticmethod
    def generate_timestamp() -> int:
        return int(time.time() * 1000)

    '''
    # Class Method
    '''
    def __init__(
        self: "BasicWebSocketManager",
        api_key: str | None = None,
        secret_key: str | None = None,
        endpoint: str | None = None,
        ws_name: str = "BaseWebSocketManager",
        ping_interval: int = 5,
        connection_interval: int = 10,
        ping_timeout: int = 10,
        conn_timeout: int = 30,
        default_callback: Callable | None = None,
    ) -> None:
        """
        func __init__():
            - instantiate the WebSocketManager class

        params:
            - callback_function: function, general callback_function for entire response from the endpoint
            - endpoint: MexC Websocket API endpoint
            - ws_name: WebSocketName
            - api_key: api_key for API usage
            - secret_key: secret_key for API usage
            - ping_interval: WebSocketConnection ping interval, default 20 seconds
            - ping_timeout: if there is no response for ping resposne for 10 seconds, close the websocket with the endpoint
            - retries: retries for WebSocket Connection for error
                # TODO: need to implement the automatic reconnect and restart (by default)
                # TODO: error handling not yet implemented
            - restart_on_error: retries on error
            - conn_timeout: WebSocket will try to connect to the endpoint for the timeout interval
            - login_required: if the websocket needs to authenticate to the system or not

        return None
        """
        try:
            self.ws_name: str = ws_name
            self.endpoint: str | None = endpoint
            self.api_key: str | None = api_key
            self.secret_key: str | None = secret_key
            self.ping_interval: int = ping_interval
            self.ping_timeout: int = ping_timeout
            self.callback_function: Callable | None = default_callback
            self.conn_interval: int = connection_interval
            self.conn_timeout: int = conn_timeout
            self.callback_dictionary: dict = dict()
            self.subscriptions: list = list()
            self.threads: list[threading.Thread] = list()
            self.auth: bool = False if (self.api_key is None or self.secret_key is None) else True
            self._stop_event = threading.Event()

        except Exception as e:
            operation_logger.error(f"{__name__} - func __init__(): {str(e)}")

        return None

    def _set_up_threads(self: "BasicWebSocketManager") -> None:
        """
        Create connection and ping threads and add them to self.threads list
        """
        # thread for connection
        wst: threading.Thread = threading.Thread(
            name = "Connection thread",
            target = lambda: self.ws.run_forever(ping_interval = 0),
            daemon = False,
        )

        # thread for ping
        wsp = threading.Thread(
            name = "Ping thread",
            target = lambda: self._ping_loop(),
            daemon = False,
        )

        self.threads.extend([wst, wsp])
        return

    def _start_threads(self: "BasicWebSocketManager") -> None:
        """
        Start all threads in self.threads list
        """
        for thread in self.threads:
            thread.start()
            time.sleep(1)
        return

    def _clean_up_threads(self: "BasicWebSocketManager") -> None:
        """
        Join and remove all threads from self.threads list
        """
        operation_logger.info(f"{__name__} - Cleaning up {len(self.threads)} threads")

        # Signal threads to stop
        self._stop_event.set()

        # Get current thread to avoid self-join deadlock
        current = threading.current_thread()

        # Join threads with timeout
        for thread in list(self.threads):
            # Skip if it's the current thread (avoid deadlock)
            if thread is current:
                operation_logger.info(f"{__name__} - Skipping current thread ({thread.name})")
                continue

            if thread.is_alive():
                operation_logger.info(f"{__name__} - Waiting for {thread.name} to finish...")
                thread.join(timeout = 2.0)

                if thread.is_alive():
                    operation_logger.warning(f"{__name__} - {thread.name} did not stop cleanly")
                else:
                    operation_logger.info(f"{__name__} - {thread.name} stopped successfully")

        # Remove all threads from list
        self.threads.clear()
        operation_logger.info(f"{__name__} - All threads cleaned up and removed")
        return

    def _connect(
        self: "BasicWebSocketManager",
    ) -> None:
        """
        Connect WebSocketApp to the API endpoint
        """
        self._clean_up_threads()

        # Reset stop event for new threads
        self._stop_event.clear()

        infinite_reconnect: bool = True
        self._closing = False

        # Create new WebSocketApp
        self.ws: websocket.WebSocketApp = websocket.WebSocketApp(
            url = self.endpoint,
            on_message = self.__on_message,
            on_open = self.__on_open,
            on_close = self.__on_close,
            on_error = self.__on_error,
        )

        time.sleep(1)

        self._set_up_threads()
        self._start_threads()

        # Wait until connected
        while (infinite_reconnect or self.conn_timeout) and not self._is_connected():
            if not infinite_reconnect:
                self.conn_timeout -= 1

            time.sleep(1)

            if not self.conn_timeout:
                operation_logger.warning(
                    f"{__name__}: connection to the host time out. You may restart the entire program."
                )
                return

        operation_logger.info(
            f"{__name__} - func _connect: Websocket Connection to the host has been established."
        )

        if self.auth:
            time.sleep(1)
            self._authenticate()

        return None

    def _authenticate(self: "BasicWebSocketManager",) -> None:
        """
        func authenticate():
            - authenticate the WebSocket connection to the API endpoint
            - login to the endpoint for private endpoint

        param self:
            - self: the instance of the class

        return None
        """
        # create the timestamp
        timestamp: str = str(BasicWebSocketManager.generate_timestamp())

        # hmac using sha256
        signature = self._generate_signature(timestamp=timestamp)

        # make the parameter dictionary into json string
        header = json.dumps(
            dict(
                subscribe = False,
                method = "login",
                param = dict(
                    apiKey = self.api_key,
                    reqTime = timestamp,
                    signature = signature,
                ),
            )
        )
        self.ws.send(header)  # send the header to the endpoint
        return None

    def _generate_signature(
        self: "BasicWebSocketManager",
        timestamp: str | None = None,
    ) -> str | None:
        """
        func generate_signature():
            - generate the signature for the private API endpoint
        """
        if not timestamp:
            timestamp = str(int(time.time() * 1000))

        if (self.api_key and self.secret_key):
            _query_str = self.api_key + timestamp

            return hmac.new(
                self.secret_key.encode("utf-8"),
                _query_str.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()

        return

    def _are_connections_connected(self: "BasicWebSocketManager", connections: list) -> bool:
        """
        func _are_connections_connected():
            - check if the connection is connected to the endpoint or not

        param: connections
            - check the connection status of the connections

        return bool
            - if there is connection which is not connected, return False
            - if all of the connections are connected, return True
        """
        for connection in connections:
            if not connection.is_connected():
                return False
        return True

    def _set_callback(
        self: "BasicWebSocketManager",
        topic: str,
        callback_function: Callable | None = None,
    ) -> None:
        """
        func _set_callback():
            - It sets the callback function for the specific topic and save it into the directory in the class
            - For response handling

        param topic
            - the topic for the callback function
            - e.g., "ticker", "order", "trade", etc.
        param callback
            - function to be called when there is a new data.

        return
        """
        self.callback_dictionary[topic] = callback_function
        return None

    # get the callback function according to the topic
    def _get_callback(
        self: "BasicWebSocketManager",
        topic: str,
    ) -> Callable | None:
        """
        func _get_callback():
            - get the callback function for the specific topic from the callback_directory in the class
            - if there is no callback function, return None

        param topic:
            - key for the dictionary where the callback function is saved.
            - e.g., "ticker", "order", "trade", etc.

        return Callable or None
            - if there is no such topic stored in the dictionary, return None
            - if there is such topic, return the callback function for that topic
        """
        return self.callback_dictionary.get(topic)

    def _is_connected(
        self: "BasicWebSocketManager",
    ):
        """
        # method: _is_connected()
            # check if the socket is connected to the endpoint or not
        """
        try:
            sock = getattr(self, "ws", None) and self.ws.sock
            return sock and sock.connected
        except AttributeError:  # exception handling, if there is any error occurred just return False
            return False

    """
    ######################################################################################################################
    #                                Websocket Message Handling Function                                                 #
    ######################################################################################################################
    """

    def __on_message(self, wsa, message):
        """
        # Parsing the message from the server
        """
        # parsing the message into the json
        response = json.loads(message)

        # now response is parsed as a dictionary so that we can do something with it.
        if (self.callback_function):
            return self.callback_function(response)

        return

    def __on_error(self: "BasicWebSocketManager", wsa, exception):
        """
        # when there is an error
            # Exit and raise errors OR
            # attempt to reconnect
        """
        operation_logger.error(
            f"{__name__} - WebSocket API: Unknown Error Occurred: {exception}"
        )
        sys.exit()
        return

    def __on_open(self: "BasicWebSocketManager", wsa):
        """
        # when the websocket is open
        """
        operation_logger.info(f"{__name__} - WebSocket has been opened")
        return

    def __on_close(self: "BasicWebSocketManager", wsa, status_code, close_msg):
        """
        # websocket close
        # logging the status code and the msg into the operation_logger
        """
        operation_logger.warning(
            f"{__name__} - the websocket has been closed: {status_code} - {close_msg}. {self.ws_name} will try to reconnect."
        )

        if not self.endpoint:
            operation_logger.error(
                f"{__name__} - {self.ws_name} lost connection but no previous URL recorded; manual restart required."
            )
            raise RuntimeError(f"{__name__} - {self.ws_name} lost connection but no previous URL recorded; manual restart required.")

        # Try to reconnect
        for attempt, delay in enumerate((0, 0.5, 1.0), start=1):
            if delay:
                time.sleep(delay)

            try:
                operation_logger.info(
                    f"{__name__} - Attempting to reconnect ({attempt}) to {self.endpoint}"
                )
                self._connect()
                operation_logger.info(
                    f"{__name__} - {self.ws_name} reconnected successfully."
                )
                break
            except Exception as e:
                operation_logger.error(
                    f"{__name__} - {self.ws_name} reconnect attempt {attempt} failed: {str(e)}"
                )
        else:
            operation_logger.critical(
                f"{__name__} - {self.ws_name} could not re-establish the websocket connection."
            )
            raise RuntimeError(f"{__name__} - {self.ws_name} could not re-establish the websocket connection; manual restart is needed.")

        self._resubscribe()
        return

    def subscribe(
        self: "BasicWebSocketManager",
        method: str,
        callback_function: Callable = None,
        param: dict | None = None,  # do not modify the param
    ):
        if (param is None):
            param = dict()

        query = dict(method = method, param = param)

        self._check_callback(query)

        while not self._is_connected() and not self.ws:
            time.sleep(0.1)

        # make dict into json, so that it can be on the header of the HTTP Socket.
        header = json.dumps(query)
        self.ws.send(header)

        # set the callback function for specific topic
        # if there is no given callback function, we just put _print_normal_msg as a callback function
        if method:  # just in case
            self._set_callback(method.replace("sub.", ""), callback_function)

        # operation_logger.info(f"new sub has been established: {self.subscriptions}")
        return

    def _resubscribe(self: "BasicWebSocketManager") -> None:
        """
        Resend cached subscriptions after the connection has been re-established.
        """
        if not self.subscriptions:
            raise RuntimeError(f"{__name__} - {self.ws_name} could not re-establish the websocket connection; manual restart is needed.")

        for query in self.subscriptions:
            try:
                method: str = query.get("method")
                self._method_subscribe(
                    method = method,
                    param = query.get("param"),
                    callback = self.callback_dictionary.get(method.replace("sub.", "")),
                    is_retry = True,
                )
            except Exception as e:
                operation_logger.critical(
                    f"{__name__} - {self.ws_name} could not resubscribe the query: {query} with the following error msg: {str(e)}"
                )
        return

    def _method_subscribe(self, method, callback, param: dict = {}, is_retry: bool = False,):
        """ """
        if not self.is_connected():
            # if there is no websocket object that has been established.
            self.__initialize_websocket()

        if (not is_retry):
            params: dict = dict(
                method = method,
                param = param,
            )
            self.subscriptions.append(
                params
            )

            self.callback_dictionary[method.replace("push.", "").replace("sub.", "")] = callback

        self.subscribe(
            method = method,
            callback_function = callback,
            param = param,
        )
        return

    def _ping_loop(
        self: "BasicWebSocketManager",
        ping_payload: str = '{"method":"ping"}',
    ) -> None:
        """
        Ping loop that checks stop event
        """
        curr_timestamp: int = 0

        # Check stop event instead of infinite loop
        while not self._stop_event.is_set() and self._is_connected():
            if (BasicWebSocketManager.generate_timestamp() - curr_timestamp > (self.ping_interval * 1_000)):
                try:
                    if self._is_connected():
                        self.ws.send(ping_payload)
                        curr_timestamp = BasicWebSocketManager.generate_timestamp()
                except Exception as e:
                    operation_logger.warning(f"{__name__} - Ping failed: {str(e)}")

        operation_logger.info(f"{__name__} - Ping loop stopped")
        return None

    def _reset(
        self: "BasicWebSocketManager",
    ):
        """
        # _reset the WebSocket when reset signal incurred
            # e.g., when there is error and we need to reset the entire program
        """
        # clear the list of subscritpions and the callback function
        self.subscriptions.clear()
        self.callback_dictionary.clear()
        self.auth = False
        operation_logger.info(f"{__name__} - WebSocket {self.ws_name} has been reset.")
        return

    def exit(
        self: "BasicWebSocketManager",
    ):
        """
        Close the websocket and clean up threads
        """
        try:
            if hasattr(self, 'ws') and self.ws:
                self.ws.close()

            # ✅ NEW: Clean up threads before exit
            self._clean_up_threads()

            operation_logger.warning(
                "The WebSocket Manager has been terminated cleanly"
            )
        except Exception as e:
            operation_logger.error(f"{__name__} - Error during exit: {str(e)}")

        return
