import threading
import time

import pandas as pd

from src.core.models.constants import MA_WRITE_PERIODS
from src.core.models.index import Index, IndexType
from src.data.index_factory import IndexFactory
from src.infrastructure.logging.set_logger import get_adapter, get_logger
from src.interfaces.pipeline_interface import PipelineController

logger = get_logger(__name__)


class DataProcessor:
    """
    - calculate the ema, sma
    - pass it to the pipeline
    """

    @classmethod
    def generate_timestamp(cls) -> int:
        return int(time.time() * 1_000)

    def __init__(
        self,
        price_data: pd.DataFrame,
        lock_price_data: threading.Lock,
        pipeline_controller: PipelineController[
            dict[str, int | IndexType, dict[int, float]]
        ],
        index_factory: IndexFactory = IndexFactory(),  # dependency injection would work.
        name: str | None = None,
    ) -> None:
        """
        - func __init__():
            - initialize the Data Processor
        """
        self.name: str = name if name else "DATA_PROCESSOR"
        self.logger = get_adapter(logger, f"{self.__class__.__name__}_{self.name}")

        self.threads: list[threading.Thread] = []
        self._stop: threading.Event = threading.Event()
        self.lock_price_data: threading.Lock = lock_price_data
        self.__index_factory: IndexFactory = index_factory
        self.pipeline_controller: PipelineController[Index] = pipeline_controller
        self.price_data: pd.DataFrame = price_data

    def start(self) -> None:
        try:
            self.__initialize_threads()
            self.__start_threads()
            self.logger.info(f"[DATA_INIT] {self.name} | Status: ready")
        except Exception as e:
            self.logger.critical(
                f"[DATA_ERROR] start() | Error: {type(e).__name__}: {e!s}"
            )

    def stop(self) -> None:
        """
        Gracefully stop the processor thread.
        """
        self.logger.info(f"[SHUTDOWN] {self.name} stopping...")
        self._stop.set()

    def __initialize_threads(self) -> None:
        """
        func __initialize_threads():
            - initialize the threads

        param self
            - DataProcessor instance

        return None

        The list of threads are as follows for the DataProcessor:
            - calculate the simplave moving averages
            - push the data to the data pipeline
        """
        try:
            # Separate?
            # to calculate and construct Index and push them to the IndexPipeline
            index_thread: threading.Thread = threading.Thread(
                target=self._push_moving_averages,
                name="index_thread",
                daemon=True,
            )
            self.logger.info(f"[THREAD_START] {index_thread.name} | Status: running")

            self.threads.extend([index_thread])
        except (RuntimeError, TypeError, AttributeError, MemoryError) as e:
            self.logger.error(
                f"[THREAD_ERROR] fail to make instances for the thread: {e!s}"
            )
        except Exception as e:
            self.logger.error(f"[THREAD_ERROR] Unexpected error starting thread: {e!s}")

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
                self.logger.critical(
                    f"[THREAD_ERROR] {thread.name} failed | Error: {type(e).__name__}: {e!s}"
                )
                raise RuntimeError
            except Exception as e:
                self.logger.critical(
                    f"[THREAD_ERROR] Unexpected error starting thread: '{thread.name}': {e!s}"
                )
                raise Exception

    def __push_indexes(self, indexes: list[Index]) -> bool:
        """
        - pass the indexes, e.g., EMA, SMA, and PRICE for now, to the IndexPipeline.
        """
        try:
            for index in indexes:
                if index:
                    self.pipeline_controller.push(index)
                    self.logger.debug(
                        f"[DATA_STATS] Type: {index.index_type.name} | Timestamp: {index.timestamp} | Status: pushed"
                    )
            return True
        except Exception as e:
            self.logger.warning(
                f"[DATA_ERROR] __push_indexes() | Error: {type(e).__name__}: {e!s}"
            )
        return

    # Data Processor
    def __calculate_ema_sma_price(
        self,
        periods: tuple[
            int, ...
        ] = MA_WRITE_PERIODS,  # this will be just used. -> default input.
    ) -> tuple[dict[str, float | int | IndexType]] | None:
        """
        - Calculate SMA, EMA, Price, and Volatility (Normalized StdDev).
        """
        try:
            current_ts = self.generate_timestamp()
            cutoff_ts = current_ts - (periods[-1] * 1_000)

            with self.lock_price_data:
                if self.price_data.shape[0] == 0:
                    return None
                mask = self.price_data.index >= cutoff_ts
                tmp_dataframe = self.price_data.loc[mask, "price"].copy()

            sma: dict[int, float] = {}
            ema: dict[int, float] = {}
            volatility: dict[int, float] = {}
            price: dict[int, float] = {
                0: float(tmp_dataframe.iloc[-1])
            }

            for period in periods:
                period_ms = period * 1_000
                period_cutoff_ts = current_ts - period_ms

                window = tmp_dataframe[tmp_dataframe.index >= period_cutoff_ts]

                if len(window) < 2:
                    continue

                data_span = window.index.max() - window.index.min()
                if data_span < period_ms * 0.8:
                    continue

                mean_val = float(window.mean())
                sma[period] = mean_val
                ema[period] = float(window.ewm(span=period, adjust=False).mean().iloc[-1])

                # Volatility: H-L% — (max - min) / last_price * 100
                # This is the real-time equivalent of a candle's (high - low) / close.
                # Matches the backtest metric so the optimized threshold (0.21%)
                # transfers directly. Old std/mean produced 0.003-0.04% on short
                # windows — far too small to be useful as a chop filter.
                high_val = float(window.max())
                low_val = float(window.min())
                last_price = float(window.iloc[-1])
                volatility[period] = ((high_val - low_val) / last_price) * 100 if last_price > 0 else 0.0

            timestamp: int = self.generate_timestamp()

            smas: dict[str, float | IndexType | dict[int, float]] = {
                "data": sma,
                "timestamp": timestamp,
                "type": IndexType.SMA,
            }

            emas: dict[str, float | IndexType | dict[int, float]] = {
                "data": ema,
                "timestamp": timestamp,
                "type": IndexType.EMA,
            }

            volatilities: dict[str, float | IndexType | dict[int, float]] = {
                "data": volatility,
                "timestamp": timestamp,
                "type": IndexType.VOLATILITY,
            }

            prices: dict[str, float | IndexType | dict[int, float]] = {
                "data": price,
                "timestamp": timestamp,
                "type": IndexType.PRICE,
            }

            return smas, emas, prices, volatilities

        except KeyError as e:
            # Specific error handling for KeyError, i.e., missing collumn
            self.logger.error(
                f"[DATA_ERROR] __calculate_ema_sma_price() | Error: KeyError: {e}"
            )
            return None

        except IndexError as e:
            # Specific error handling for IndexError, i.e., out of range and slicing of the DataFrame.
            self.logger.error(
                f"[DATA_ERROR] __calculate_ema_sma_price() | Error: IndexError: {e}"
            )
            return None

        except Exception as e:
            self.logger.warning(
                f"[DATA_ERROR] __calculate_ema_sma_price() | Error: {type(e).__name__}: {e!s}."
            )
            return None

    """
    ##################
    # Get Ticker Data and Put Them in the Buffer
    ##################
    """

    def _put_ticker_data(
        self,
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
                block=False,
                timeout=None,
            )
            return
        except Exception as e:
            self.logger.critical(
                f"[DATA_ERROR] _put_ticker_data() | Error: {type(e).__name__}: {e!s}"
            )
        return

    # Data Processor
    def _push_moving_averages(
        self,
    ) -> None:
        """
        func _push_moving_averages():
            - call the function __calculate_ema_sma_price() to calculate the EMA and SMA
            - get tuple of data where:
                - data[0] = SMA values
                - data[1] = EMA values
            - when the data is available, push the data to the data pipeline.
        """
        # TODO: Need to change this.
        while not self._stop.is_set():
            data: (
                tuple[
                    dict[int, float],
                    dict[int, float],
                    dict[int, float],
                    dict[int, float],
                ]
                | None
            ) = self.__calculate_ema_sma_price()

            if data:
                sma_values: Index = self.__index_factory.generate_index(data[0])
                ema_values: Index = self.__index_factory.generate_index(data[1])
                price: Index = self.__index_factory.generate_index(data[2])
                volatility: Index = self.__index_factory.generate_index(data[3])

                indexes: list[Index,] = [sma_values, ema_values, price, volatility]

                # TODO: need to change -> other wrapper which can get the result and push to the data pipeline.
                self.__push_indexes(indexes)

            time.sleep(2)
