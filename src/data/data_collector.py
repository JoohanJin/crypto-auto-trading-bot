import time
import threading
import pandas as pd
from queue import Queue

from src.interfaces.websocket_interface import WebSocketInterface
from src.infrastructure.logging.set_logger import get_logger, get_adapter
from src.core.models.service_dto import Ticker

logger = get_logger(__name__)


class DataCollector:
    '''
    - Fetch the data from the broker
    '''
    @staticmethod
    def generate_timestamp() -> int:
        '''
        - return the current timestamp in ms in int.
        '''
        return int(time.time() * 1_000)

    def __init__(
        self,
        websocket_interface: WebSocketInterface,  # assume that only fetches the price data.
        price_data: pd.DataFrame,
        lock_price_data: threading.Lock,
        name: str | None = None,
    ) -> None:
        self.name: str = name if name else "DATA_COLLECTOR"
        self.logger = get_adapter(logger, f"{self.__class__.__name__}_{self.name}")
        
        self.wsi: WebSocketInterface = websocket_interface
        time.sleep(1)

        # Initialize DataFrame with explicit schema to avoid FutureWarning
        self.price_data: pd.DataFrame = price_data
        
        self.lock_price_data: threading.Lock = lock_price_data

        self.threads: list[threading.Thread] = []
        self._stop: threading.Event = threading.Event()

        self.price_fetch_buffer: Queue = Queue()
        return

    def start(self) -> None:
        self.wsi.ticker(callback = self._put_ticker_data)

        self.__initialize_threads()
        self.__start_threads()
        return

    def stop(self) -> None:
        """
        Gracefully stop the collector thread and unblock the queue.
        """
        self.logger.info(f"[SHUTDOWN] {self.name} stopping...")
        self._stop.set()
        # Unblock the get() call in the background thread
        self.price_fetch_buffer.put(None)
        return

    def __initialize_threads(self) -> None:
        try:
            # start the thread for the data fetch from the API
            thread_price_fetch: threading.Thread = threading.Thread(
                name = "price_data_fetch",
                target = self._price_data_fetch,
                daemon = True
            )
            self.logger.info(f"[THREAD_START] {thread_price_fetch.name} | Status: running")

            self.threads.extend(
                [
                    thread_price_fetch,
                ]
            )
        except (RuntimeError, TypeError, AttributeError, MemoryError) as e:
            self.logger.error(f"[THREAD_ERROR] fail to make instances for the thread: {str(e)}")
        except Exception as e:
            self.logger.critical(f"[THREAD_ERROR] Unexpected error constructing thread pool - {str(e)}")

        return

    def __start_threads(self) -> None:
        """
        func _start_threads():
            - start the threads in the thread pool of the class.
            - Will raise issues if there is  problem with the triggering of the thread.

        param self: dataCollectorAndProcessor
            - class object

        return None
        """
        for thread in self.threads:
            try:
                thread.start()
                self.logger.info(f"[THREAD_START] {thread.name} | Status: running")
            except RuntimeError as e:
                self.logger.critical(f"[THREAD_ERROR] {thread.name} failed | Error: {type(e).__name__}: {str(e)}")
                raise RuntimeError
            except Exception as e:
                self.logger.critical(
                    f"[THREAD_ERROR] Unexpected error starting thread: '{thread.name}': {str(e)}"
                )
                raise
        return

    """
    ######################################################################################################################
    #                                     Get Ticker Data and Put Them in the Buffer                                     #
    ######################################################################################################################
    """

    # Data processor
    def _put_ticker_data(
        self,
        msg: Ticker,
    ) -> None:
        """
        ;This function is a callback for ticker of the WebSocket
        func _put_ticker_data():
            - Put price data of the crypto into the buffer.

        param self: DataCollectorAndProcessor
            - class object
        param msg: dict
            - message from the MexC API, json format, but parsed as python dict.

        return None
        """
        try:
            self.price_fetch_buffer.put(
                msg,
                block = False,
                timeout = None,
            )
            return
        except Exception as e:
            self.logger.critical(
                f"[DATA_ERROR] _put_ticker_data() | Error: {type(e).__name__}: {str(e)}"
            )
        return

    """
    ######################################################################################################################
    #                                   Get the Ticker Data from the Data Buffer                                         #
    ######################################################################################################################
    """
    # DataFetcher
    def _get_data_buffer(
        self,
    ) -> dict | None:
        """
        func _get_data_buffer():
            - Get the data from the buffer and return it.
            - if there is no data in the buffer, then wait until the data is available.
            - if there is an error then, return None
        """
        try:
            # price_fetch_buffer is a queue.
            result = self.price_fetch_buffer.get(block = True)

            return result
        except Exception as e:
            self.logger.critical(f"[DATA_ERROR] _get_data_buffer() | Error: {type(e).__name__}: {str(e)}")
            return None

    # data fetcher
    def _price_data_fetch(
        self,
    ) -> None:
        """
        func _price_data_fetch():
            - It continuously fetches data from the queue, processes it and appends it to the DataFrame.
            - the processing includes the followings:
                - change the data to a dataframe
                - get the timestamp
                - set the timestamp as an index of the dataframe
                - concatenate the dataframe to the entire data buffer.
        """
        while not self._stop.is_set():
            try:
                response: Ticker | None = (
                    self._get_data_buffer()
                )  # data from the data buffer

                if isinstance(response, Ticker):  # Type Checking
                    # in-place modification to keep the same DataFrame reference
                    with self.lock_price_data:
                        self.price_data.loc[response.timestamp] = {
                            "symbol": f"{response.ticker.ticker}_{response.ticker.quote}",
                            "price": response.price,
                        }

            except Exception as e:
                self.logger.critical(
                    f'[DATA_ERROR] _price_data_fetch() | Error: {type(e).__name__}: {str(e)}'
                )
        return
