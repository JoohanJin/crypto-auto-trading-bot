import time
import threading
import pandas as pd
from queue import Queue

from src.brokers.mexc.future import FutureWebSocket
from src.infrastructure.logging.set_logger import operation_logger


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
        self: "DataCollector",
        websocket: FutureWebSocket,  # assume that only fetches the price data.
        price_data: pd.DataFrame,
        lock_price_data: threading.Lock,
    ) -> None:
        self.ws: FutureWebSocket = websocket  # make this into interface
        time.sleep(1)

        self.price_data: pd.DataFrame = price_data
        self.lock_price_data: threading.Lock = lock_price_data

        self.threads: list[threading.Thread] = list()

        self.price_fetch_buffer: Queue = Queue()
        return

    def start(self: "DataCollector") -> None:
        self.ws.ticker(callback = self._put_ticker_data)

        self.__initialize_threads()
        self.__start_threads()
        return

    def __initialize_threads(self: "DataCollector") -> None:
        try:
            # start the thread for the data fetch from the API
            thread_price_fetch: threading.Thread = threading.Thread(
                name = "price_data_fetch",
                target = self._price_data_fetch,
                daemon = True
            )
            operation_logger.info(f"{__name__} - {self.__class__.__name__} - Thread for price fetch has been set up!")

            # thread_memory_save: threading.Thread = threading.Thread(
            #     name = "resize_df",
            #     target = self._resize_df,
            #     daemon = True
            # )
            # operation_logger.info(
            #     f"{__name__} - {self.__class__.__name__} - Thread for DataFrame size limit has been set up!"
            # )

            self.threads.extend(
                [
                    thread_price_fetch,
                    # thread_memory_save,
                ]
            )
        except (RuntimeError, TypeError, AttributeError, MemoryError) as e:
            operation_logger.error(f"{__name__} - {self.__class__.__name__} - fail to make instances for the thread: {str(e)}")
        except Exception as e:
            operation_logger.critical(f"{__name__}: Unexpected error constructing thread pool - {str(e)}")

        return

    def __start_threads(self: "DataCollector") -> None:
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
                operation_logger.info(
                    f"{__name__} - {self.__class__.__name__} - Thread '{thread.name}' (ID: {thread.ident}) has started"
                )
            except RuntimeError as e:
                operation_logger.critical(
                    f"{__name__} - {self.__class__.__name__} - Failed to start thread '{thread.name}': {str(e)}"
                )
                raise RuntimeError
            except Exception as e:
                operation_logger.critical(
                    f"{__name__} - {self.__class__.__name__} - Unexpected error starting thread: '{thread.name}': {str(e)}"
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
        self: 'DataCollector',
        msg: dict,
    ) -> None:
        """
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
                msg.get("data"),
                block = False,
                timeout = None,
            )
            return
        except Exception as e:
            operation_logger.critical(
                f"{__name__} - {self.__class__.__name__} Error in class {self.__class__.__name__} in method _put_ticker_data(): {e}"
            )
        return

    """
    ######################################################################################################################
    #                                   Get the Ticker Data from the Data Buffer                                         #
    ######################################################################################################################
    """

    # DataFetcher
    def _get_data_buffer(
        self: 'DataCollector',
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
            operation_logger.critical(
                f"{__name__} - Error retreving data from queue: {e}"
            )
            return None

    # data fetcher
    def _price_data_fetch(
        self: 'DataCollector',
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
        while True:
            try:
                response: dict | None = (
                    self._get_data_buffer()
                )  # data from the data buffer
                if response:
                    # TODO: store 'riseFallRates' and 'riseFallRatesTimezone'
                    # timestamp = response["timestamp"]

                    # make `the data, dictionary, into the pandas dataframe.
                    tmp = pd.DataFrame(
                        data = [response],
                    )

                    # set the timestamp as the index of the dataframe.
                    tmp.set_index("timestamp", inplace = True)

                    # merge the new dataframe to the existing dataframe.
                    with self.lock_price_data:
                        self.price_data = pd.concat([self.price_data, tmp], axis = 0)

            except Exception as e:
                operation_logger.critical(
                    f'Unexpected Error Occurred in function "_price_data_fetch": {e}'
                )
        return
