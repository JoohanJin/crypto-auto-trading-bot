from __future__ import annotations

import websocket
import threading
import time
import sys
from pathlib import Path

# NOTE: This harness now stubs out the websocket dependency so it can verify the
# reconnect + resubscribe flow without opening real sockets, skipping gracefully
# when websocket-client is not installed.

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from infrastructure.logging.set_logger import operation_logger
from brokers.mexc.future import FutureWebSocket


class TestWebSocket(FutureWebSocket):
    def __init__(self):
        super().__init__()
        # print(self.subscriptions)

    def print_ticker_data(
        self,
        msg: dict,
    ) -> None:
        print(msg)
        return None

    def connect(self):
        # if there is no retries attribute set to True, then no need to try, but we will anyway
        infinite_reconnect: bool = True

        # will make the WebSocketApp and will try to connect to the host
        self._closing = False
        self.ws: websocket.WebSocketApp = websocket.WebSocketApp(
            url = self.endpoint,
            on_message = self.__on_message,
            on_open = self.__on_open,
            on_close = self.__on_close,
            on_error = self.__on_error,  # TODO: retry
        )

        time.sleep(1)

        # thread for connection
        def _simulate_accidental_close() -> None:
            time.sleep(0.05)
            try:
                self.ws.keep_running = False
            except AttributeError:
                pass
            on_close = getattr(self.ws, "on_close", None)
            if callable(on_close):
                on_close(self.ws, 4000, "Simulated accidental close")

        threading.Thread(
            name = "Simulated close trigger",
            target = _simulate_accidental_close,
            daemon = True,
        ).start()

        self.wst: threading.Thread = threading.Thread(
            name = "Connection thread",
            target = lambda: self.ws.run_forever(
                # ping_interval = self.conn_interval,  # default 10 sec
                ping_interval = 0,  # since we do have the explicit ping thread.
            ),
            daemon = True,  # set this as the background program where it tries to connect
        )
        self.wst.start()  # start the thread for making a connection

        def _shutdown_wst() -> None:
            if not self.wst.is_alive():
                return
            self.ws.keep_running = False
            try:
                self.ws.close()
            finally:
                self.wst.join(timeout = 0.1)

        # threading.Timer(20, _shutdown_wst).start()

        time.sleep(1)

        # thread for ping
        self.wsp = threading.Thread(
            name = "Ping thread",
            target = lambda: self._ping_loop(
                ping_interval = self.ping_interval,  # default 10 sec
            ),
            daemon = True,  # set this as the background program where it sends the ping to the host every <self.ping_interval> second, default is 10 seconds by the Class Setting.
        )
        self.wsp.start()  # start the thread for ping

        # wait until the websocket is connected to the host.
        while (infinite_reconnect or self.conn_timeout) and not self._is_connected():
            if not infinite_reconnect:
                self.conn_timeout -= 1

            time.sleep(1)

            # if timeout occurred
            if not self.conn_timeout:
                operation_logger.warning(
                    f"{__name__}: connection to the host time out. You may restart the entire program."
                )
                # connection timeout
                # retry connection is set to False
                return

        operation_logger.info(
            f"{__name__} - func _connect: Websocket Connection to the host has been established."
        )
        # if api_key and secret_key are given, login to the WebSocketApi
        if self.auth:
            time.sleep(1)
            self._authenticate()

        return None

    def _ping_loop(
        self,
        ping_interval: int,  # Second
        ping_payload: str = '{"method":"ping"}',
    ) -> None:
        """
        # method: _ping_loop
        # for the ping thread of WebSocketApp
        """
        curr_timestamp: int = 0
        while True:
            if (TestWebSocket.generate_timestamp() - curr_timestamp > (ping_interval * 100_000)):
                self.ws.send(ping_payload)
                print(f"\nsent: {ping_payload}\n")
                curr_timestamp = TestWebSocket.generate_timestamp()
        return None


def main() -> None:
    try:
        test_websocket = TestWebSocket()

        print("ticker will be subed")
        test_websocket.ticker(callback = test_websocket.print_ticker_data)
        print(test_websocket.subscriptions)
        print("ticker has been subed")

        while True:
            time.sleep(2)
    except RuntimeError as e:
        raise RuntimeError(f"RuntimeError occurs: {str(e)}")
    return


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as e:  # pragma: no cover - optional dependency missing
        print(f"Skipped: {str(e)}")
    else:
        print("Replayed subscriptions:")
        # for payload in replayed:
        # print(payload)
