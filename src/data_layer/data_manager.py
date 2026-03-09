# Standard Module

import threading
import time
from queue import Queue
from typing import Any

import pandas as pd

from src.core.models.index import IndexType
from src.data_layer.data_collector import DataCollector
from src.data_layer.data_processor import DataProcessor
from src.data_layer.data_saver import DataSaver
from src.infrastructure.logging.set_logger import get_adapter, get_logger
from src.interfaces.pipeline_interface import PipelineController

# Custom Module
from src.interfaces.websocket_interface import WebSocketInterface


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
        pipeline_controller: PipelineController[
            dict[str, int | IndexType, dict[int, float]]
        ],
        name: str | None = None,
    ):
        self.name: str = name if name else "DATA_MANAGER"
        self.logger = get_adapter(logger, f"{self.__class__.__name__}_{self.name}")

        self._memory_saver: DataSaver = DataSaver()  # can be here.
        self.price_fetch_buffer: Queue[dict[str, Any]] = Queue()

        self.threads: list[threading.Thread] = []

        self.lock_price_data: threading.Lock = threading.Lock()
        self._stop: threading.Event = threading.Event()

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

        self.logger.info(f"[DATA_INIT] {self.name} | Status: ready")

    def start(
        self,
    ) -> None:
        # Threads
        self.__initialize_threads()
        self.__start_threads()

        # Components of the class
        self.collector.start()
        self.processor.start()

    def stop(self) -> None:
        """
        Gracefully stop all data threads and child components.
        """
        self.logger.info(f"[SHUTDOWN] {self.name} stopping...")
        self._stop.set()
        if hasattr(self.collector, "stop"):
            self.collector.stop()
        if hasattr(self.processor, "stop"):
            self.processor.stop()

    def __initialize_threads(self) -> None:
        try:
            thread_memory_save: threading.Thread = threading.Thread(
                name="resize_df", target=self.__resize_df, daemon=True
            )
            self.logger.info(
                f"[THREAD_START] {thread_memory_save.name} | Status: running"
            )

            self.threads.append(
                thread_memory_save,
            )
        except (RuntimeError, TypeError, AttributeError, MemoryError) as e:
            self.logger.error(
                f"[THREAD_ERROR] fail to make instances for the thread: {e!s}"
            )
        except Exception as e:
            self.logger.critical(
                f"[THREAD_ERROR] Unexpected error constructing thread pool - {e!s}"
            )

    def __start_threads(self) -> None:
        for thread in self.threads:
            try:
                thread.start()
                self.logger.info(f"[THREAD_START] {thread.name} | Status: running")
            except RuntimeError as e:
                self.logger.critical(
                    f"[THREAD_ERROR] Failed to start thread - '{thread.name}': {e!s}"
                )
                raise RuntimeError
            except Exception as e:
                self.logger.critical(
                    f"[THREAD_ERROR] Unexpected error starting thread - '{thread.name}': {e!s}"
                )
                raise

    def __resize_df(
        self,
        wait_time: int = 300,  # in seconds, 5 minutes by default
    ) -> None:
        """
                func __resize_df():
                    - using _data_saver to move the dataframe storing the price movement to the csv file in data
        `
                make a use of data saver, i.e., custom class using the df.to_csv()

                params self: DataCollectorAndProcessor
                    - class object

                return None
        """
        curr_timestamp = self.generate_timestamp()
        retention_ms = 60 * 60 * 1_000  # 1 hour in milliseconds
        while not self._stop.is_set():
            data = None
            try:
                if self.generate_timestamp() - curr_timestamp > (
                    wait_time * 1_000
                ):  # Five minutes
                    with self.lock_price_data:
                        cutoff_ts = self.generate_timestamp() - retention_ms
                        # Index is timestamp (epoch ms) — drop rows older than 1 hour
                        old_mask = self.prices.index < cutoff_ts
                        old_count = old_mask.sum()
                        if old_count > 0:
                            # Drop in-place to preserve DataFrame reference for other components
                            self.prices.drop(self.prices.index[old_mask], inplace=True)
                            self.logger.info(
                                f"[DATA_CLEANUP] Action: resized | Rows: {self.prices.shape[0]} | "
                                f"Cleaned: {old_count} | Retention: 1h"
                            )
                        else:
                            self.logger.info(
                                f"[DATA_CLEANUP] Action: skipped | Rows: {self.prices.shape[0]} | "
                                f"All within 1h retention window"
                            )

                    # TODO: store the data to the database -> possibly just resize it and put the new data into the db.
                    curr_timestamp = self.generate_timestamp()
            except Exception as e:
                self.logger.warning(
                    f"[DATA_ERROR] __resize_df() | Error: {type(e).__name__}: {e!s}"
                )
