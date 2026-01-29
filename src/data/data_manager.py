# Standard Module

import time
from typing import Any, Dict
import pandas as pd
import threading
from queue import Queue

# Custom Module
from brokers.mexc.future import FutureWebSocket
from infrastructure.logging.set_logger import operation_logger
from data.data_saver import DataSaver
from core.models.index import IndexType
from data.data_collector import DataCollector
from data.data_processor import DataProcessor
from interfaces.pipeline_interface import PipelineController


class DataManager:
    def generate_timestamp(self,) -> int:
        """
        static func generate_timestamp():
            - Generate the timestamp using the current time, in the form of epoch in ms.

        param None

        return int
            - the timestam in the form of epoch in ms.
        """
        return int(time.time() * 1_000)

    def __init__(
        self: "DataManager",
        websocket: FutureWebSocket,
        pipeline_controller: PipelineController[dict[str, int | IndexType, dict[int, float]]],
        memory_count_limit: int = 2_000,
    ):
        self._memory_saver: DataSaver = DataSaver()  # can be here.
        self.price_fetch_buffer: Queue[Dict[str, Any]] = Queue()
        self._df_size_limit: int = memory_count_limit

        self.threads: list[threading.Thread] = list()

        self.lock_price_data: threading.Lock = threading.Lock()
        # default dataframe with the given columns
        self.price_data: pd.DataFrame = pd.DataFrame(
            columns=[
                "symbol",
                "lastPrice",
                "riseFallRate",
                "fairPrice",
                "indexPrice",
                "volume24",
                "amount24",
                "maxBidPrice",
                "minAskPrice",
                "lower24Price",
                "high24Price",
                "bid1",
                "ask1",
                "holdVol",
                "riseFallValue",
                "fundingRate",
                "zone",
                "riseFallRates",
                "riseFallRatesOfTimezone",
            ],
            index = [self.generate_timestamp()],
        )
        self.price_data.index.name = "timestamp"  # force the index name

        self.collector: DataCollector = DataCollector(
            websocket = websocket,
            price_data = self.price_data,
            lock_price_data=self.lock_price_data,
        )
        self.processor: DataProcessor = DataProcessor(
            price_data = self.price_data,
            lock_price_data = self.lock_price_data,
            pipeline_controller = pipeline_controller,
        )

        self.start()

        return

    def start(self: "DataManager",) -> None:
        # Threads
        self.__initialize_threads()
        self.__start_threads()

        # Components of the class
        self.collector.start()
        self.processor.start()
        return

    def __initialize_threads(self: "DataManager",) -> None:
        try:
            thread_memory_save: threading.Thread = threading.Thread(
                name = "resize_df",
                target = self.__resize_df,
                daemon = True
            )
            operation_logger.info(
                f"{__name__}: Thread for DataFrame size limit has been set up!"
            )

            self.threads.append(thread_memory_save,)
        except (RuntimeError, TypeError, AttributeError, MemoryError) as e:
            operation_logger.error(
                f"{__name__} - {self.__class__.__name__} - fail to make instances for the thread: {str(e)}"
            )
        except Exception as e:
            operation_logger.critical(
                f"{__name__}: Unexpected error constructing thread pool - {str(e)}"
            )

        return

    def __start_threads(self: "DataManager",) -> None:
        for thread in self.threads:
            try:
                thread.start()
                operation_logger.info(
                    f"{__name__} - {self.__class__.__name__} - Thread '{thread.name}' (ID: {thread.ident}) has started"
                )
            except RuntimeError as e:
                operation_logger.critical(
                    f"{__name__} - {self.__class__.__name__} - Failed to start thread - "
                    f"'{thread.name}' (ID: {thread.ident}): {str(e)}"
                )
                raise RuntimeError
            except Exception as e:
                operation_logger.critical(
                    f"{__name__} - {self.__class__.__name__} - Unexpected error "
                    f"starting thread - '{thread.name}' (ID: {thread.ident}): {str(e)}"
                )
                raise
        return

    # Data Fetcher? -> let's make the separate class.
    def __resize_df(
        self: 'DataManager',
        wait_time: int = 300,  # in seconds, 5 minutes by default
    ) -> None:
        """
        func __resize_df():
            - using _data_saver to move the dataframe storing the price movement to the csv file in data

        make a use of data saver, i.e., custom class using the df.to_csv()

        params self: DataCollectorAndProcessor
            - class object

        return None
        """
        curr_timestamp = self.generate_timestamp()
        while True:
            data = None
            try:
                if (self.generate_timestamp() - curr_timestamp > (wait_time * 1_000)):  # Five minutes
                    with self.df_lock:
                        if self.price_data.shape[0] > self._df_size_limit:
                            data = self.price_data.iloc[: -self._df_size_limit]
                            self.price_data = self.price_data.iloc[-self._df_size_limit :]
                            operation_logger.info(
                                f"{__name__} - {self.__class__.__name__} Data Saver resized price DataFrame to "
                                f"{self.price_data.shape[0]} rows and {self.price_data.shape[1]} columns - "
                                f"cleaned {data.shape[0]} rows and {data.shape[1]} columns"
                            )
                        else:
                            operation_logger.info(
                                f"{__name__} - {self.__class__.__name__} - Data Saver skipped cleanup - "
                                f"size below threshold: {self.price_data.shape[0]} rows"
                            )

                    # TODO: store the data to the database -> possibly just resize it and put the new data into the db.
                    curr_timestamp = self.generate_timestamp()
            except Exception as e:
                operation_logger.warning(
                    f"{__name__} - func _resize_df(): Exception caused: {str(e)}"
                )

        return None
