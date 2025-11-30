# Standard Module
import time
from typing import Dict, Tuple
import pandas as pd
import threading
from queue import Queue

# Custom Module
from mexc.future import FutureWebSocket
from logger.set_logger import operation_logger
from manager.data_saver import DataSaver
from object.constants import MA_WRITE_PERIODS, IndexType
from src.object.index import Index
from interface.pipeline_interface import PipelineController


'''
# Index Structure
# Dict[str, int | IndexType | Dict]

{
    "timestamp": DataCollectorAndProcessor.generate_timestamp(),
    "type": IndexType.SMA,
    "data": data,
}
'''


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


class DataCollectorAndProcessor:
    '''
    ######################################################################################################################
    #                                               Static Method                                                        #
    ######################################################################################################################
    '''
    @staticmethod
    def generate_timestamp() -> int:
        """
        static func generate_timestamp():
            - Generate the timestamp using the current time, in the form of epoch in ms.

        param None

        return int
            - the timestam in the form of epoch in ms.
        """
        return int(time.time() * 1_000)

    '''
    ######################################################################################################################
    #                                               Instance Method                                                      #
    ######################################################################################################################
    '''
    def __init__(
        self: "DataCollectorAndProcessor",
        pipeline_controller: PipelineController[dict[str, int | IndexType, dict[int, float]]],
        websocket: FutureWebSocket,  # assume that only fetches the price data.
        index_factory: IndexFactory = IndexFactory(),  # dependency injection would work.
        memory_count_limit: int = 2_000,
    ) -> None:
        """
        func __init__() for StrategyManager
            - set the WebSocket() for data fetching
                - set the subscription for the ticker data.
            - set the DataSaver() for control of the DataFrame Size.
            - set the Threads pool for the necessary operations for the Strategy Manager.
            - set the Telegram Bot for the automated log system.
            - set the DataBuffer for the price buffer.
            - set the Price Data Table

        params self
            - class object
        params pipeline
            - pipeline to transmit the data to the StrategyManager.

        return None

        - it will automatically connect the websocket to the host
        - and will continue to keep the connection between the client and host
        - no need to provide api_key and secret_key, i.e., no authentication on API side for data fetching.
        """
        self.ws: FutureWebSocket = websocket
        self._ma_period: int = 20  # ! No need to be here I think.
        self._memory_saver: DataSaver = DataSaver()  # can be here.
        self._df_size_limit: int = memory_count_limit
        self.threads: list[threading.Thread] = list()
        self.pipeline_controller: PipelineController[Index] = pipeline_controller
        self.__index_factory: IndexFactory = index_factory

        # wait till WebSocket set up is done
        time.sleep(1)

        # used as buffer for data fetching from the MEXC Endpoint
        self.price_fetch_buffer = Queue()

        # subsribe to the ticker data from the MexC data
        self.ws.ticker(callback = self._put_ticker_data)

        # lock for accessing Price DataFrame.
        self.df_lock = threading.Lock()

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
            index = [DataCollectorAndProcessor.generate_timestamp()],  # ! use the static method for timestamp generation
        )
        self.price_data.index.name = "timestamp"  # force the index name

        # ! start the operation in the initialization process.
        self.start()

        return

    """
    ######################################################################################################################
    #                                               Threading Management                                                 #
    ######################################################################################################################
    """
    def start(
        self: "DataCollectorAndProcessor",
    ) -> None:
        self._init_threads()  # initialize the thread pool
        self._start_threads()  # start the thread after all the thread pool is there.
        return

    def _init_threads(
        self: 'DataCollectorAndProcessor',
    ) -> None:
        """
        func _init_threads():
            - set the threads for the necessary operations and append them into the list of thread pool

        params self
            - class object

        return None

        The list of threads are as follows:
            - price fetching
                - get the price from the broker
            - calculate the simple moving average
                - calculate the simple moving average based on the
            - memory saver
                - used to control the size of the Price DataFrame.

        return None
        """
        try:
            # start the thread for the data fetch from the API
            thread_price_fetch: threading.Thread = threading.Thread(
                name = "price_data_fetch",
                target = self._price_data_fetch,
                daemon = True
            )
            operation_logger.info(f"{__name__}: Thread for price fetch has been set up!")

            thread_calculate_sma: threading.Thread = threading.Thread(
                name = "provide_moving_average_thread",
                target = self._push_moving_averages,
                daemon = True,
            )
            operation_logger.info(
                f"{__name__}: Thread for calculating sma has been set up!"
            )

            thread_memory_save: threading.Thread = threading.Thread(
                name = "resize_df",
                target = self._resize_df,
                daemon = True
            )
            operation_logger.info(
                f"{__name__}: Thread for DataFrame size limit has been set up!"
            )

        except (RuntimeError, TypeError, AttributeError, MemoryError) as e:
            operation_logger.critical(f"{__name__}: fail to make instances for the thread - {str(e)}")

        except Exception as e:
            operation_logger.critical(f"{__name__}: Unexpected error constructing thread pool - {str(e)}")

        self.threads.extend(
            [
                thread_price_fetch,
                thread_calculate_sma,
                thread_memory_save,
            ]
        )
        return

    def _start_threads(
        self: 'DataCollectorAndProcessor',
    ) -> None:
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
                    f"{__name__}: Thread '{thread.name}' (ID: {thread.ident}) has started"
                )
            except RuntimeError as e:
                operation_logger.critical(
                    f"{__name__}: Failed to start thread '{thread.name}': {str(e)}"
                )
                raise RuntimeError
            except Exception as e:
                operation_logger.critical(
                    f"{__name__}: Unexpected error starting thread: '{thread.name}': {str(e)}"
                )
                raise
        return

    """
    ######################################################################################################################
    #                                     Get Ticker Data and Put Them in the Buffer                                     #
    ######################################################################################################################
    """

    def _put_ticker_data(
        self: 'DataCollectorAndProcessor',
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

    """
    ######################################################################################################################
    #                                   Get the Ticker Data from the Data Buffer                                         #
    ######################################################################################################################
    """

    def _price_data_fetch(
        self: 'DataCollectorAndProcessor',
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
                    with self.df_lock:
                        self.price_data = pd.concat([self.price_data, tmp], axis = 0)

            except Exception as e:
                operation_logger.critical(
                    f'Unexpected Error Occurred in function "_price_data_fetch": {e}'
                )
        return

    def _get_data_buffer(
        self: 'DataCollectorAndProcessor',
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

    # for batch processing of the data.
    def __append_df(
        self: 'DataCollectorAndProcessor',
        data_buffer: list,
        timestamp_buffer: list,
    ) -> bool:
        """
        func __append_df():
            - Make the data as an Pandas dataframe.
            - store the dataframe into the list, for the batch processing
        """
        try:
            tmp = pd.DataFrame(
                data_buffer,
                index = [timestamp_buffer],
            )

            with self.df_lock:
                self.price_data = pd.concat(
                    [self.price_data, tmp],
                    axis = 0,
                )

            # ! need to make it to raise a custom exception.
            return True
        except Exception as e:
            operation_logger.critical(
                f"{__name__} - Error in appending the data to the DataFrame: {e}"
            )
            return False
        finally:
            data_buffer.clear()
            timestamp_buffer.clear()

    """
    ######################################################################################################################
    #                                  Calculate the SMAs Using Data From the Buffer                                     #
    ######################################################################################################################
    """

    def _push_moving_averages(
        self: 'DataCollectorAndProcessor',
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

    def __calculate_ema_sma_price(
        self: 'DataCollectorAndProcessor',
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
            with self.df_lock:
                if self.price_data.shape[0] == 0:
                    return None
                tmp_dataframe = self.price_data[-periods[-1] :]["fairPrice"].copy()

            sma:   Dict[int, float] = dict()  # oh.. make the dictionary object and put it.
            ema:   Dict[int, float] = dict()
            price: float = tmp_dataframe.iloc[-1]  # just last price data.

            # TODO: this should be fast enough, but can be optimized further.
            for period in periods:
                window = tmp_dataframe.tail(period)
                if len(window) < period:
                    break
                sma[period * 2] = float(window.mean())
                ema[period * 2] = float(window.ewm(span = period, adjust = False).mean().iloc[-1])

            timestamp: int = DataCollectorAndProcessor.generate_timestamp()

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
    #                                  Resize the DataFrame holding the Price Info                                       #
    ######################################################################################################################
    """

    def _resize_df(
        self: 'DataCollectorAndProcessor',
    ) -> None:
        """
        func __resize_df():
            - using _data_saver to move the dataframe storing the price movement to the csv file in data

        make a use of data saver, i.e., custom class using the df.to_csv()

        params self: DataCollectorAndProcessor
            - class object

        return None
        """
        curr_timestamp = DataCollectorAndProcessor.generate_timestamp()
        while True:
            data = None
            try:
                if (DataCollectorAndProcessor.generate_timestamp() - curr_timestamp > (300 * 1_000)):  # Five minutes
                    with self.df_lock:
                        if self.price_data.shape[0] > self._df_size_limit:
                            data = self.price_data.iloc[: -self._df_size_limit]
                            self.price_data = self.price_data.iloc[-self._df_size_limit :]
                            operation_logger.info(
                                f"{__name__} - Data Saver resized price DataFrame to "
                                f"{self.price_data.shape[0]} rows and {self.price_data.shape[1]} columns - "
                                f"cleaned {data.shape[0]} rows and {data.shape[1]} columns"
                            )
                        else:
                            operation_logger.info(
                                f"{__name__} - Data Saver skipped cleanup; size below threshold: "
                                f"{self.price_data.shape[0]} rows"
                            )

                    # TODO: add the proper database.
                    # Disable the .csv generation for now.
                    # if data is not None:
                    #     self._memory_saver.write(data)
                    #     operation_logger.info(
                    #         f"{__name__} - Data Saver has stored the recent price data: size: {data.shape[0]} rows and {data.shape[1]} columns"
                    #     )

                    curr_timestamp = DataCollectorAndProcessor.generate_timestamp()
            except Exception as e:
                operation_logger.warning(
                    f"{__name__} - func _resize_df(): Exception caused: {str(e)}"
                )

        return None

    """
    ######################################################################################################################
    #                                        Push Data to the Data Pipeline                                              #
    ######################################################################################################################
    """

    def __push_ema_data(
        self: 'DataCollectorAndProcessor',
        data: Index,
    ) -> bool:
        return self.pipeline_controller.push(
            {
                "timestamp": DataCollectorAndProcessor.generate_timestamp(),
                "type": IndexType.EMA,
                "data": data,
            }
        )

    def __push_sma_data(
        self: 'DataCollectorAndProcessor',
        data: Index,
    ) -> bool:
        return self.pipeline_controller.push(
            {
                "timestamp": DataCollectorAndProcessor.generate_timestamp(),
                "type": IndexType.SMA,
                "data": data,
            }
        )

    def __push_price_data(
        self: 'DataCollectorAndProcessor',
        data: Index,
    ):
        return self.pipeline_controller.push(
            {
                "timestamp": DataCollectorAndProcessor.generate_timestamp(),
                "type": IndexType.PRICE,
                "data": data,
            }
        )

    def __push_indexes(
        self: 'DataCollectorAndProcessor',
        indexes: list[Index]
    ) -> bool:
        try:
            for index in indexes:
                if (index):
                    self.pipeline_controller.push(index)
            return True
        except Exception as e:
            operation_logger.warning(f"{__name__} - Unexpected Exception Orccured: {str(e)}")
