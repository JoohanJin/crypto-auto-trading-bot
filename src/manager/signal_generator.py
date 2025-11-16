# TODO: Need to re-plan the structure of Signal generator.
# STANDARD LIBRARY
import threading
from typing import Dict, List
import time

# CUSTOM LIBRARY
from object.indexes import Index
from custom_telegram.telegram_bot_class import CustomTelegramBot
from logger.set_logger import operation_logger, trading_logger
from object.signal import TradeSignal, Signal
from interface.pipeline_interface import PipelineController
from object.constants import IndexType


class SignalGenerator:
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

    @staticmethod
    def start_threads(threads: list[threading.Thread]) -> None:
        for thread in threads:
            try:
                # start the thread.
                thread.start()
                operation_logger.info(
                    f"{__name__} - Thread '{thread.name}' (ID: {thread.ident}) has started"
                )
            except RuntimeError as e:
                operation_logger.critical(
                    f"{__name__} - Failed to start thread '{thread.name}': {str(e)}"
                )
                raise RuntimeError(f"Failed to start thread '{thread.name}': {str(e)}")
            except Exception as e:
                operation_logger.critical(
                    f"{__name__} - Unexpected error starting thread: '{thread.name}': {str(e)}"
                )
                raise Exception(
                    f"Unexpected error starting thread: '{thread.name}': {str(e)}"
                )
        return

    '''
    ######################################################################################################################
    #                                               Function Method                                                      #
    ######################################################################################################################
    '''
    def __init__(
        self: 'SignalGenerator',
        data_pipeline_controller: PipelineController[dict[str, int | IndexType, dict[int, float]]],
        signal_pipeline_controller: PipelineController[dict[str, int | TradeSignal]],
        custom_telegram_bot: CustomTelegramBot,
        signal_window: int = 5_000,
    ) -> None:
        """
        func __init__():
            - Initialize the Strategy Handler.
            - It gets the pipeline as a parameter for the indicator fetching.
            - It initializes the telegram bot for the notification.
            - It initializes the threads for the indicator fetching.

        param self: StrategyHandler
            - class object
        param pipeline: DataPipeline
            - Data pipeline for the indicator fetching.

        return None
        """
        # data pipeline to get the indicators
        self.data_pipeline_controller:   PipelineController[dict[str, int | IndexType, dict[int, float]]] = data_pipeline_controller
        self.signal_pipeline_controller:          PipelineController[dict[str, int | object.TradeSignal]] = signal_pipeline_controller

        # telegram bot manager to send the notification.
        self.__telegram_bot: CustomTelegramBot = custom_telegram_bot

        # Shared Structure
        # Mutex Lock
        self.indicators_lock: threading.Lock = threading.Lock()
        self.indicators: dict[IndexType, dict[int, float]] = {
            IndexType.SMA: None,  # Latest SMA data
            IndexType.EMA: None,  # latest EMA data
            IndexType.PRICE: None,  # latest Price data
        }

        # threads pool
        self.threads: List[threading.Thread] = list()

        # Start
        self.start()

        return None

    def start(self: "SignalGenerator") -> None:
        # initialize the threads
        self._init_threads()
        # start each thread, which is in the threads pool.
        SignalGenerator.start_threads(self.threads)
        return

    """
    ######################################################################################################################
    #                                                 Threads Management                                                 #
    ######################################################################################################################
    """

    def _init_threads(
        self: 'SignalGenerator',
    ):
        """
        - func _init_threads:
            - Initialize the threads for the indicator fetching.
            - It will be used to initialize the threads for the indicator fetching.
            - It will be used to consume the data and generate the signals based on the data and pass it to the signal pipeline.

        - param self: StrategyHandler

        - return None
        """
        index_thread: threading.Thread = threading.Thread(
            name = 'index_data_getter',
            target = self.get_data,
            daemon = True,
        )
        operation_logger.info(
            f"{__name__}: Thread for index data getter has been set up!"
        )

        self.threads.extend(
            [
                index_thread,
            ]
        )

        return None

    """
    ######################################################################################################################
    #                                      Read Data from the Data Pipeline                                              #
    ######################################################################################################################
    """
    def get_data(
        self: 'SignalGenerator',
    ) -> None:
        while True:
            try:
                data: Index = self.data_pipeline_controller.pop(block = True,)
                # print(f"{data.index_type}: {data.data}")
                if (data):
                    with self.indicators_lock:
                        self.indicators[data.index_type] = data.data
            except Exception as e:
                operation_logger.critical(f"{__name__} -  Unexpected Exeption occured - {str(e)}")

        return

    def push_signal(self: "SignalGenerator", signal: Signal) -> None:
        try:
            self.signal_pipeline_controller.push(signal)
        except Exception as e:
            operation_logger.critical(f"{__name__} - Cannot put signal to the queue: {str(e)}")


class StrategyManager:
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

    @staticmethod
    def __generate_signal(
        signal: TradeSignal,
    ) -> Signal:
        """
        - func __generate_signal():
            - Generate the signal based on the data.
            - It will be used to generate the signal based on the data.

        - param self: StrategyHandler
            - class object
        - param signal: object.TradeSignal
            - the signal object to be generated.

        - return indicator
        """
        return Signal(
            signal = signal,
        )

    @staticmethod
    def start_threads(threads: list[threading.Thread]) -> None:
        for thread in threads:
            try:
                # start the thread.
                thread.start()
                operation_logger.info(
                    f"{__name__} - Thread '{thread.name}' (ID: {thread.ident}) has started"
                )
            except RuntimeError as e:
                operation_logger.critical(
                    f"{__name__} - Failed to start thread '{thread.name}': {str(e)}"
                )
                raise RuntimeError(f"Failed to start thread '{thread.name}': {str(e)}")
            except Exception as e:
                operation_logger.critical(
                    f"{__name__} - Unexpected error starting thread: '{thread.name}': {str(e)}"
                )
                raise Exception(
                    f"Unexpected error starting thread: '{thread.name}': {str(e)}"
                )
        return

    def __init__(self: "StrategyManager", signal_window = 5_000,) -> None:
        # shared data structure to store Timestamp of the previoius invokation of each signal.
        self.signal_timestamps: dict[str, int] = dict()
        self.signal_timestamps_lock: threading.Lock = threading.Lock()
        self.signal_window: int = signal_window
        self.threads: list[threading.Thread] = list()

        self.start()
        return

    def start(self: "StrategyManager") -> None:
        # if this is the thread-based class
        self.__init_threads()
        StrategyManager.start_threads(self.threads)

    def analyze_index(self: "StrategyManager", ) -> None:
        # What to return? -> list of Signtal?
        return

    def __init_threads(self: "StrategyManager") -> None:
        # Consume the data.
        golden_cross_thread: threading.Thread = threading.Thread(
            name = "golden_cross_signal_generator",
            target = self.generate_golden_cross_signal,
            daemon = True,
        )
        operation_logger.info(
            f"{__name__}: Thread for golden_cross_signal_generator has been set up!"
        )

        death_cross_thread: threading.Thread = threading.Thread(
            name = "death_cross_signal_generator",
            target = self.generate_death_cross_signal,
            daemon = True,
        )
        operation_logger.info(
            f"{__name__}: Thread for death_cross_signal_generator has been set up!"
        )

        price_ma_thread: threading.Thread = threading.Thread(
            name = "price_ma_signal_generator",
            target = self.generate_price_moving_average_signal,
            daemon = True,
        )
        operation_logger.info(
            f"{__name__}: Thread for price_ma_signal_generator has been set up!"
        )

        ema_sma_divergence_thread: threading.Thread = threading.Thread(
            name = "ema_sma_divergence_signal_generator",
            target = self.generate_ema_sma_divergence_signal,
            daemon = True,
        )
        operation_logger.info(
            f"{__name__}: Thread for ema_sma_divergence_signal_generator has been set up!"
        )

        price_reversal_thread: threading.Thread = threading.Thread(
            name = "price_reversal_signal_generator",
            target = self.generate_price_reversal_signal,
            daemon = True,
        )
        operation_logger.info(
            f"{__name__}: Thread for price_reversal_signal_generator has been set up!"
        )

        # add data consumptions threads into the Threads pool.
        self.threads.extend(
            [
                golden_cross_thread,
                death_cross_thread,
                price_ma_thread,
                ema_sma_divergence_thread,
                price_reversal_thread,
            ]
        )

        return

    """
    ######################################################################################################################
    #                                                Generating Signal                                                   #
    ######################################################################################################################
    """

    def generate_golden_cross_signal(
        self: 'StrategyManager',
    ) -> None:
        """
        - func generate_golden_cross_signal():
            - function to generate the golden cross signal generator.

        - A golden cross occurs when:
            - a short-term moving average (SMA) crosses above
            - a long-term moving average, indicating a potential bullish trend.
        """
        key: str = "golden_cross"
        while True:
            with self.indicators_lock:
                sma_data: dict | None = self.indicators.get(IndexType.SMA)
                ema_data: dict | None = self.indicators.get(IndexType.EMA)

            with self.signal_timestamps_lock:
                prev_timestamp: int = self.signal_timestamps.get(key, 0)

            curr_timestamp: int = StrategyManager.generate_timestamp()

            if (curr_timestamp - prev_timestamp > self.signal_window) and (sma_data and ema_data):  # only need to check if the sma and ema data are available.
                # generate the signal based on the data and passit to the signal pipeline.
                ten_sec_sma: float | None = sma_data.get(10)
                five_min_ema: float | None = ema_data.get(300)

                if ten_sec_sma and five_min_ema:
                    if ten_sec_sma > five_min_ema:
                        # generate the signal
                        signal: Signal = StrategyManager.__generate_signal(
                            signal = TradeSignal.LONG_TERM_BUY
                        )
                        trading_logger.info(
                            f"{__name__} - Golden Cross Signal has been generated!: Bullish Trend."
                        )

                with self.signal_timestamps_lock:
                    self.signal_timestamps[key] = curr_timestamp

            time.sleep(1.5)
        return None

    def generate_death_cross_signal(
        self: 'StrategyManager',
    ) -> None:
        """
        - func generate_death_cross_signal():
            - function to generate the death cross signal generator.

        - A death cross occurs when:
            - a short-term moving average crosses below
            - a long-term moving average,
            - indicating a potential bearish trend.
        """
        key: str = "death_cross"
        while True:
            with self.indicators_lock:
                sma_data: dict = self.indicators.get(IndexType.SMA, None)
                ema_data: dict = self.indicators.get(IndexType.EMA, None)

            with self.signal_timestamps_lock:
                prev_timestamp: int = self.signal_timestamps.get(key, 0)
            curr_timestamp: int = SignalGenerator.generate_timestamp()

            if (
                curr_timestamp - prev_timestamp > self.signal_window
            ) and (
                sma_data and ema_data
            ):  # only need to check if the sma and ema data are available.
                # generate the signal based on the data and passit to the signal pipeline.
                ten_sec_sma: float | None = sma_data.get(10)
                five_min_ema: float | None = ema_data.get(300)

                if ten_sec_sma and five_min_ema:
                    if ten_sec_sma < five_min_ema:
                        # generate the signal
                        signal: Signal = StrategyManager.__generate_signal(
                            signal=TradeSignal.LONG_TERM_SELL
                        )
                        trading_logger.info(
                            f"{__name__} - Death Cross Signal has been generated!: Bearish Trend."
                        )

                with self.signal_timestamps_lock:
                    self.signal_timestamps[key] = curr_timestamp

            time.sleep(1.5)
        return None

    def generate_price_moving_average_signal(
        self: 'StrategyManager',
    ) -> None:
        """
        - func generate_price_moving_average_signal():
            - function to generate the price moving average signal generator.

        - Moving Average:
            - when the current price crosses above or below a specified MA.
            - This signal can indicate potential buy or sell opportunities based on the direction of the price movement relative to the moving average.

        - Compare the current price with the moving average.
            - If the current price crosses above the moving average, generate a "Price Above MA" signal.
            - If the current price crosses below the movign average, generate a "Price Below MA" signal.
        """
        key: str = "price_moving_average"
        while True:
            with self.indicators_lock:
                sma_data: Dict[int, float] = self.indicators.get(IndexType.SMA)
                current_price:       float = self.indicators.get(IndexType.PRICE)

            with self.signal_timestamps_lock:
                prev_timestamp: int = self.signal_timestamps.get(key, 0)

            curr_timestamp: int = StrategyManager.generate_timestamp()

            if (
                curr_timestamp - prev_timestamp > self.signal_window
            ) and (
                sma_data and current_price
            ):
                sma_60 = sma_data.get(60)  # Example for 1 min SMA

                if sma_60:
                    if current_price > sma_60:
                        signal: Signal = StrategyManager.__generate_signal(
                            signal = TradeSignal.SHORT_TERM_BUY,
                        )
                        trading_logger.info(
                            f"{__name__} - Short Term Buy Signal has been generated!: Bullish Trend."
                        )

                    elif current_price < sma_60:
                        signal: Signal = StrategyManager.__generate_signal(
                            signal=TradeSignal.SHORT_TERM_SELL,
                        )
                        trading_logger.info(
                            f"{__name__} - Short Term Sell Signal has been generated!: Bearish Trend."
                        )

                with self.signal_timestamps_lock:
                    self.signal_timestamps[key] = curr_timestamp

            time.sleep(1.5)
        return None

    def generate_ema_sma_divergence_signal(
        self: 'StrategyManager',
        threshold: float = 0.05,
    ) -> None:
        """
        - func generate_ema_sma_divergence_signal():
            - function to generate the EMA and SMA divergence signal generator.

        - param threshold: float
            - the threshold value to determine the divergence between EMA and SMA

        - Divergence:
            - There is a significant difference between the EMA and SMA.
            - This divergence can indicate potential changes in makret trends or momentum.
        """
        key: str = "ema_sma_divergence"
        while True:
            with self.indicators_lock:
                sma_data: Dict[int, float] = self.indicators.get(IndexType.SMA)
                ema_data: Dict[int, float] = self.indicators.get(IndexType.EMA)

            with self.signal_timestamps_lock:
                prev_timestamp: int = self.signal_timestamps.get(key, 0)
            curr_timestamp: int = StrategyManager.generate_timestamp()

            if (curr_timestamp - prev_timestamp > self.signal_window) and (
                sma_data and ema_data
            ):
                sma_60 = sma_data.get(60)  # data for 1 min SMA
                ema_60 = ema_data.get(60)  # data for 1 min EMA

                if sma_60 and ema_60:
                    divergence: float = abs(sma_60 - ema_60)
                    if divergence > threshold:
                        signal: Signal = StrategyManager.__generate_signal(
                            signal=TradeSignal.HOLD,
                        )
                        trading_logger.info(
                            f"{__name__} - Divergence Signal has been generated!: Potential Trend Change."
                        )

                with self.signal_timestamps_lock:
                    self.signal_timestamps[key] = curr_timestamp

            time.sleep(1.5)
        return None

    def generate_price_reversal_signal(
        self: 'StrategyManager',
    ) -> None:
        """
        - func generate_price_reversal_signal():
            - function to generate the price reversal signal generator.

        - A price reversal signal occurs when:
            - the price changes direction after a sustained trend.
            - This cna indicate potential buy or sell opportunities based on this.
        """
        key: str = "price_reversal"
        while True:
            with self.indicators_lock:
                sma_data: Dict[int, float] = self.indicators.get(IndexType.SMA)
                current_price: float = self.indicators.get(IndexType.PRICE)

            with self.signal_timestamps_lock:
                prev_timestamp: int = self.signal_timestamps.get(key, 0)
            curr_timestamp: int = StrategyManager.generate_timestamp()

            if ((curr_timestamp - prev_timestamp > self.signal_window) and (sma_data and current_price)):
                sma_60: float = sma_data.get(60)

                if sma_60:
                    if current_price > sma_60:
                        signal: Signal = StrategyManager.__generate_signal(
                            signal = TradeSignal.SHORT_TERM_BUY,
                        )
                        trading_logger.info(
                            f"{__name__} - Price Reversal Signal has been generated!: Bullish Reveral."
                        )
                    elif current_price < sma_60:
                        signal: Signal = StrategyManager.__generate_signal(
                            signal = TradeSignal.SHORT_TERM_SELL,
                        )
                        trading_logger.info(
                            f"{__name__} - Price Reversal Signal has been generated!: Bearish Reveral."
                        )

                with self.signal_timestamps_lock:
                    self.signal_timestamps[key] = curr_timestamp

            time.sleep(1.5)
        return None
