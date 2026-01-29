import time
import threading
from typing import Dict, Tuple
import pandas as pd

from src.infrastructure.logging.set_logger import operation_logger
from src.interfaces.pipeline_interface import PipelineController
from src.core.models.constants import MA_WRITE_PERIODS, IndexType
from src.core.models.index import Index


class IndexFactory:
    '''
    # factory which generates the Index data type.
    # what does it do?
        # check the validity of index Dict?
        # generate the timestamp?
    '''
    @staticmethod
    def generate_timestamp() -> int:
        return int(time.time() * 1_000)

    def __init__(
        self: "IndexFactory",
        # index: Dict[str, int | IndexType | Dict[int, float]],
    ) -> None:
        return

    def generate_index(
        self: "IndexFactory",
        index: Dict[str, int | IndexType | Dict[int, float]],
    ) -> Index | None:
        timestamp: int = index.get("timestamp", IndexFactory.generate_timestamp())
        index_type: IndexType | None = index.get("type", None)
        data: Dict[int, float] | None = index.get("data", None)

        if (index_type and data):
            return Index(
                timestamp = timestamp,
                index_type = index_type,
                data = data,
            )
        else:
            return None


class DataProcessor:
    '''
    - calculate the ema, sma
    - pass it to the pipeline
    '''
    @staticmethod
    def generate_timestamp() -> int:
        return int(time.time() * 1_000)

    def __init__(
        self: "DataProcessor",
        price_data: pd.DataFrame,
        lock_price_data: threading.Lock,
        pipeline_controller: PipelineController[dict[str, int | IndexType, dict[int, float]]],
        index_factory: IndexFactory = IndexFactory(),  # dependency injection would work.
    ) -> None:
        '''
        - func __init__():
            - initialize the Data Processor
        '''
        self.threads: list[threading.Thread] = list()
        self.lock_price_data: threading.Lock = lock_price_data
        self.__index_factory: IndexFactory = index_factory
        self.pipeline_controller: PipelineController[Index] = pipeline_controller
        self.price_data: pd.DataFrame = price_data
        return

    def start(self: "DataProcessor") -> None:
        try:
            self.__initialize_threads()
            self.__start_threads()
        except Exception as e:
            operation_logger.critical(
                f"{__name__} - {self.__class__.__name__} - Error while starting DataProcessor: {str(e)}"
            )
        return

    def __initialize_threads(self: "DataProcessor") -> None:
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
            operation_logger.info(f"{__name__} - {self.__class__.__name__} - Thread '{index_thread.name}' (ID: {index_thread.ident}) has been created")

            self.threads.extend([index_thread])
        except (RuntimeError, TypeError, AttributeError, MemoryError) as e:
            operation_logger.error(f"{__name__} - {self.__class__.__name__} - fail to make instances for the thread: {str(e)}")
        except Exception as e:
            operation_logger.error(f"{__name__} - {self.__class__.__name__} - Unexpected error starting thread: {str(e)}")

        return

    def __start_threads(self: "DataProcessor") -> None:
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
                raise Exception
        return

    def __push_indexes(
        self: 'DataProcessor',
        indexes: list[Index]
    ) -> bool:
        '''
        - pass the indexes, e.g., EMA, SMA, and PRICE for now, to the IndexPipeline.
        '''
        try:
            for index in indexes:
                if (index):
                    self.pipeline_controller.push(index)
            return True
        except Exception as e:
            operation_logger.warning(f"{__name__} - Unexpected Exception Orccured: {str(e)}")
        return

    # Data Processor
    def __calculate_ema_sma_price(
        self: 'DataProcessor',
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
            current_ts = DataProcessor.generate_timestamp()
            cutoff_ts = current_ts - (periods[-1] * 2 * 1_000)

            with self.lock_price_data:
                if self.price_data.shape[0] == 0:
                    return None
                # tmp_dataframe = self.price_data[-periods[-1] :]["fairPrice"].copy()  # ! need to change this part
                mask = self.price_data.index >= cutoff_ts
                tmp_dataframe = self.price_data.loc[mask, "fairPrice"].copy()

            sma:   Dict[int, float] = dict()  # oh.. make the dictionary object and put it.
            ema:   Dict[int, float] = dict()
            price: float = tmp_dataframe.iloc[-1]  # just last price data.

            # TODO: this should be fast enough, but can be optimized further.
            for period in periods:
                period_seconds = period * 2 * 1_000
                period_cutoff_ts = current_ts - period_seconds

                window = tmp_dataframe[tmp_dataframe.index >= period_cutoff_ts]

                window = tmp_dataframe.tail(period)

                # if len(window) < min_data_points:  # The value of minimum data points needed?
                #     break

                sma[period * 2] = float(window.mean())
                ema[period * 2] = float(window.ewm(span = period, adjust = False).mean().iloc[-1])

            timestamp: int = DataProcessor.generate_timestamp()

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
            operation_logger.error(
                f"{__name__}: function {self.__class__.__name__}.__calculate_ema_sma_price has raised the KeyError: {e}"
            )
            return None

        except IndexError as e:
            # Specific error handling for IndexError, i.e., out of range and slicing of the DataFrame.
            operation_logger.error(
                f"{__name__}: function {self.__class__.__name__}.__calculate_ema_sma_price has raised the IndexError: {e}"
            )
            return None

        except Exception as e:
            operation_logger.warning(
                f"{__name__}: function {self.__class__.__name__}.__calculate_ema_sma_price has has raised the Unknown Exception - {str(e)}."
            )
            return None

    """
    ######################################################################################################################
    #                                     Get Ticker Data and Put Them in the Buffer                                     #
    ######################################################################################################################
    """

    def _put_ticker_data(
        self: 'DataProcessor',
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
                f"{__name__}: Error in class {self.__class__.__name__} in method _put_ticker_data(): {e}"
            )
        return

    # Data Processor
    def _push_moving_averages(
        self: 'DataProcessor',
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
