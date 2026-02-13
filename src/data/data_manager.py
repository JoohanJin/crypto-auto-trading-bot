# Standard Module

import time
from typing import Any, Dict
import pandas as pd
import threading
from queue import Queue

# Custom Module
from src.interfaces.websocket_interface import WebSocketInterface
from src.infrastructure.logging.set_logger import get_logger, get_adapter
from src.data.data_saver import DataSaver
from src.core.models.index import IndexType
from src.data.data_collector import DataCollector
from src.data.data_processor import DataProcessor
from src.interfaces.pipeline_interface import PipelineController

logger = get_logger(__name__)


class DataManager:
    @classmethod
    def generate_timestamp(cls) -> int:
        """
        static func generate_timestamp():
            - Generate the timestamp using the current time, in the form of epoch in ms.

        param None

        return int
            - the timestam in the form of epoch in ms.
        """
        return int(time.time() * 1_000)

    def __init__(
        self,
        websocket_interface: WebSocketInterface,
        pipeline_controller: PipelineController[dict[str, int | IndexType, dict[int, float]]],
        memory_count_limit: int = 2_000,
        name: str | None = None,
    ):
        self.name: str = name if name else "DATA_MANAGER"
        self.logger = get_adapter(logger, f"{self.__class__.__name__}_{self.name}")
        
        self._memory_saver: DataSaver = DataSaver()  # can be here.
        self.price_fetch_buffer: Queue[Dict[str, Any]] = Queue()
        self._df_size_limit: int = memory_count_limit

        self.threads: list[threading.Thread] = []

        self.lock_price_data: threading.Lock = threading.Lock()
    
        # default dataframe with the given columns and explicit dtypes
        self.prices: pd.DataFrame = pd.DataFrame(
            {
                "symbol": pd.Series(dtype="object"),
                "price": pd.Series(dtype="float64"),
            },
        )
        self.prices.index.name = "timestamp"

        self.collector: DataCollector = DataCollector(
            websocket_interface=websocket_interface,
            price_data=self.prices,
            lock_price_data=self.lock_price_data,
        )
        self.processor: DataProcessor = DataProcessor(
            price_data=self.prices,
            lock_price_data=self.lock_price_data,
            pipeline_controller=pipeline_controller,
        )

        self.start()

        return

    def start(self,) -> None:
        # Threads
        self.__initialize_threads()
        self.__start_threads()

        # Components of the class
        self.collector.start()
        self.processor.start()
        return

    def __initialize_threads(self) -> None:
        try:
            thread_memory_save: threading.Thread = threading.Thread(
                name = "resize_df",
                target = self.__resize_df,
                daemon = True
            )
            self.logger.info("Thread for DataFrame size limit has been set up!")

            self.threads.append(thread_memory_save,)
        except (RuntimeError, TypeError, AttributeError, MemoryError) as e:
            self.logger.error(f"fail to make instances for the thread: {str(e)}")
        except Exception as e:
            self.logger.critical(f"Unexpected error constructing thread pool - {str(e)}")

        return

    def __start_threads(self) -> None:
        for thread in self.threads:
            try:
                thread.start()
                self.logger.info(f"Thread '{thread.name}' (ID: {thread.ident}) has started")
            except RuntimeError as e:
                self.logger.critical(
                    f"Failed to start thread - '{thread.name}' (ID: {thread.ident}): {str(e)}"
                )
                raise RuntimeError
            except Exception as e:
                self.logger.critical(
                    f"Unexpected error starting thread - '{thread.name}' (ID: {thread.ident}): {str(e)}"
                )
                raise
        return

    def __resize_df(
        self,
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
                            self.logger.info(
                                f"Data Saver resized price DataFrame to "
                                f"{self.price_data.shape[0]} rows and {self.price_data.shape[1]} columns - "
                                f"cleaned {data.shape[0]} rows and {data.shape[1]} columns"
                            )
                        else:
                            self.logger.info(
                                f"Data Saver skipped cleanup - size below threshold: {self.price_data.shape[0]} rows"
                            )

                    # TODO: store the data to the database -> possibly just resize it and put the new data into the db.
                    curr_timestamp = self.generate_timestamp()
            except Exception as e:
                self.logger.warning(f"func _resize_df(): Exception caused: {str(e)}")

        return None
