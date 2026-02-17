import time
import threading
from typing import Dict, Tuple
import pandas as pd

from src.infrastructure.logging.set_logger import get_logger, get_adapter
from src.interfaces.pipeline_interface import PipelineController
from src.core.models.constants import MA_WRITE_PERIODS
from src.core.models.index import Index, IndexType
from src.data.index_factory import IndexFactory

logger = get_logger(__name__)


class DataProcessor:
    '''
    - calculate the ema, sma
    - pass it to the pipeline
    '''
    @classmethod
    def generate_timestamp(cls) -> int:
        return int(time.time() * 1_000)

    def __init__(
        self,
        price_data: pd.DataFrame,
        lock_price_data: threading.Lock,
        pipeline_controller: PipelineController[dict[str, int | IndexType, dict[int, float]]],
        index_factory: IndexFactory = IndexFactory(),  # dependency injection would work.
        name: str | None = None,
    ) -> None:
        '''
        - func __init__():
            - initialize the Data Processor
        '''
        self.name: str = name if name else "DATA_PROCESSOR"
        self.logger = get_adapter(logger, f"{self.__class__.__name__}_{self.name}")
        
        self.threads: list[threading.Thread] = []
        self.lock_price_data: threading.Lock = lock_price_data
        self.__index_factory: IndexFactory = index_factory
        self.pipeline_controller: PipelineController[Index] = pipeline_controller
        self.price_data: pd.DataFrame = price_data
        return

    def start(self) -> None:
        try:
            self.__initialize_threads()
            self.__start_threads()
            self.logger.info(f"[DATA_INIT] {self.name} | Status: ready")
        except Exception as e:
            self.logger.critical(
                f"[DATA_ERROR] start() | Error: {type(e).__name__}: {str(e)}"
            )
        return

    def __initialize_threads(self) -> None:
        '''
        func __initialize_threads():
            - initialize the threads

        param self
            - DataProcessor instance

        return None

        The list of threads are as follows for the DataProcessor:
            - calculate the simplave moving averages
            - push the data to the data pipeline
        '''
        try:
            # Separate?
            # to calculate and construct Index and push them to the IndexPipeline
            index_thread: threading.Thread = threading.Thread(
                target = self._push_moving_averages,
                name = "index_thread",
                daemon = True,
            )
            self.logger.info(f"[THREAD_START] {index_thread.name} | Status: running")

            self.threads.extend([index_thread])
        except (RuntimeError, TypeError, AttributeError, MemoryError) as e:
            self.logger.error(f"[THREAD_ERROR] fail to make instances for the thread: {str(e)}")
        except Exception as e:
            self.logger.error(f"[THREAD_ERROR] Unexpected error starting thread: {str(e)}")

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
                self.logger.info(
                    f"[THREAD_START] {thread.name} | Status: running"
                )
            except RuntimeError as e:
                self.logger.critical(
                    f"[THREAD_ERROR] {thread.name} failed | Error: {type(e).__name__}: {str(e)}"
                )
                raise RuntimeError
            except Exception as e:
                self.logger.critical(
                    f"[THREAD_ERROR] Unexpected error starting thread: '{thread.name}': {str(e)}"
                )
                raise Exception
        return

    def __push_indexes(
        self,
        indexes: list[Index]
    ) -> bool:
        '''
        - pass the indexes, e.g., EMA, SMA, and PRICE for now, to the IndexPipeline.
        '''
        try:
            for index in indexes:
                if (index):
                    self.pipeline_controller.push(index)
                    self.logger.debug(f"[DATA_STATS] Type: {index.index_type.name} | Timestamp: {index.timestamp} | Status: pushed")
            return True
        except Exception as e:
            self.logger.warning(f"[DATA_ERROR] __push_indexes() | Error: {type(e).__name__}: {str(e)}")
        return

    # Data Processor
    def __calculate_ema_sma_price(
        self,
        periods: Tuple[int, ...] = MA_WRITE_PERIODS,  # this will be just used. -> just default input.
    ) -> tuple[dict[str, float | int | IndexType]] | None:
        """
        # TODO: make a separate class fo this.
        func __calculate_ema_sma_price():
            - It calculate the Simple Moving Average (SMA) and Exponential Moving Average (EMA) of the lastPrice.

        params self: DataCollectorAndProcessor
            - class object
        params periods: Tuple[int]
            - periods for the calculation of the SMA and EMA

        return (smas, emas): Tuple[Tuple[float], Tuple[float]] | None
            - Tuple of SMA and EMA values
        """
        try:
            current_ts = self.generate_timestamp()
            cutoff_ts = current_ts - (periods[-1] * 1_000)

            with self.lock_price_data:
                if self.price_data.shape[0] == 0:
                    return None
                mask = (self.price_data.index >= cutoff_ts)
                tmp_dataframe = self.price_data.loc[mask, "price"].copy()

            sma: dict[int, float] = {}  # make the dictionary object and put it.
            ema: dict[int, float] = {}
            price: dict[int, float] = {
                0: float(tmp_dataframe.iloc[-1])
            }  # just last price data.

            # TODO: this should be fast enough, but can be optimized further.
            for period in periods:
                period_ms = period * 1_000
                period_cutoff_ts = current_ts - period_ms

                window = tmp_dataframe[tmp_dataframe.index >= period_cutoff_ts]

                # 최소 2개 데이터 필요
                if len(window) < 2:
                    continue

                # 실제 데이터 스팬 체크 (80% 이상 커버해야 함)
                data_span = window.index.max() - window.index.min()
                if data_span < period_ms * 0.8:
                    continue

                sma[period] = float(window.mean())
                ema[period] = float(window.ewm(span=period, adjust=False).mean().iloc[-1])

            timestamp: int = self.generate_timestamp()

            smas: Dict[str, float | IndexType | Dict[int, float]] = {
                "data": sma,
                "timestamp": timestamp,
                "type": IndexType.SMA,
            }

            emas: Dict[str, float | IndexType | Dict[int, float]] = {
                "data": ema,
                "timestamp": timestamp,
                "type": IndexType.EMA,
            }

            price: Dict[str, float | IndexType | Dict[int, float]] = {
                "data": price,
                "timestamp": timestamp,
                "type": IndexType.PRICE,
            }

            return smas, emas, price

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
                f"[DATA_ERROR] __calculate_ema_sma_price() | Error: {type(e).__name__}: {str(e)}."
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
                block = False,
                timeout = None,
            )
            return
        except Exception as e:
            self.logger.critical(
                f"[DATA_ERROR] _put_ticker_data() | Error: {type(e).__name__}: {str(e)}"
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
        while True:
            data: (
                Tuple[
                    Dict[int, float],
                    Dict[int, float],
                    Dict[int, float],
                ] | None
            ) = self.__calculate_ema_sma_price()

            if data:
                sma_values: Index = self.__index_factory.generate_index(data[0])
                ema_values: Index = self.__index_factory.generate_index(data[1])
                price: Index = self.__index_factory.generate_index(data[2])

                indexes: list[Index, ] = [
                    sma_values,
                    ema_values,
                    price
                ]

                # TODO: need to change -> other wrapper which can get the result and push to the data pipeline.
                self.__push_indexes(indexes)

            time.sleep(2)
        return
