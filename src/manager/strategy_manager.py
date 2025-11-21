# STANDARD LIBRARY
import threading
from typing import Callable, Dict
import time

# CUSTOM LIBRARY
from logger.set_logger import operation_logger, trading_logger
from object.constants import IndexType
from object.signal import TradeSignal, Signal
from object.indexes import Index


class StrategyManager:
    SLEEP_INTERVAL: float = 1.5

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
    def generate_signal(
        signal: TradeSignal,
    ) -> Signal:
        """
        - func generate_signal():
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

    def __init__(
        self: "StrategyManager",
        indicators: dict[IndexType, Dict[int, float] | float | None],
        indicators_lock: threading.Lock,
        push_signal_callback: Callable[[Signal], None],
        signal_window: int = 5_000,
    ) -> None:
        # shared data structure to store Timestamp of the previoius invokation of each signal.
        self.signal_timestamps: dict[str, int] = dict()
        self.signal_timestamps_lock: threading.Lock = threading.Lock()
        self.signal_window: int = signal_window
        self.threads: list[threading.Thread] = list()

        self.indicators: dict[IndexType, Index] = indicators
        self.indicators_lock: threading.Lock = indicators_lock
        self._push_signal_callback: Callable[[Signal], None] = push_signal_callback

        self.start()
        return

    def start(self: "StrategyManager") -> None:
        # if this is the thread-based class
        self.__init_threads()
        StrategyManager.start_threads(self.threads)

    def push_signal(self: "StrategyManager", signal: Signal, details: str) -> None:
        try:
            self._push_signal_callback(signal)
            trading_logger.info(
                f"{__name__} - {details} Signal has been generated."
            )
        except Exception as e:
            operation_logger.critical(
                f"{__name__} - Cannot push signal '{signal.signal.name}': {str(e)}"
            )

    def __init_threads(self: "StrategyManager") -> None:
        strategy_threads: list[tuple[str | Callable]] = [
            ("golden_cross_signal_generator", self.generate_golden_cross_signal),
            ("death_cross_signal_generator", self.generate_death_cross_signal),
            ("price_ma_signal_generator", self.generate_price_moving_average_signal),
            ("ema_sma_divergence_signal_generator", self.generate_ema_sma_divergence_signal),
            ("price_reversal_signal_generator", self.generate_price_reversal_signal),
        ]

        for name, target in strategy_threads:
            thread = threading.Thread(name=name, target=target, daemon=True)
            self.threads.append(thread)
            operation_logger.info(f"{__name__}: Thread for {name} has been set up!")

    def __verify_index(
        self: "StrategyManager",
        index: Index,
        time_window: int = 5_000,
    ) -> bool:
        if (StrategyManager.generate_timestamp() - index.timestamp < time_window):
            return True
        else:
            return False

    def __extract_data(
        self: "StrategyManager",
        index: Index,
    ) -> dict[int, float] | None:
        if index:
            return index.data
        else:
            return None

    def _get_indicator_value(
        self: "StrategyManager",
        indicator: Index | None,
        window: int,
    ) -> float | None:
        data = self.__extract_data(indicator) if indicator else None
        return data.get(window) if data else None

    def __update_signal_timestamp(
        self: "StrategyManager",
        key: str,
    ) -> None:
        with self.signal_timestamps_lock:
            self.signal_timestamps[key] = StrategyManager.generate_timestamp()
        return

    def __get_signal_timestamp(
        self: "StrategyManager",
        key: str,
    ) -> int:
        with self.signal_timestamps_lock:
            return self.signal_timestamps.get(key, 0)

    def _should_generate_signal(
        self: "StrategyManager",
        key: str,
    ) -> bool:
        """
        Check if enough time has passed since the last signal generation.

        param key: str
            - The signal identifier key

        return bool
            - True if signal should be generated, False otherwise
        """
        prev_timestamp: int = self.__get_signal_timestamp(key)
        return StrategyManager.generate_timestamp() - prev_timestamp > self.signal_window

    def _get_indicators_safely(
        self: "StrategyManager",
        *indicator_types: IndexType,
    ) -> dict[IndexType, Index | None]:
        """
        Thread-safe retrieval of multiple indicators.

        param indicator_types: IndexType
            - Variable number of indicator types to retrieve

        return dict[IndexType, Index | None]
            - Dictionary mapping indicator types to their Index objects
        """
        with self.indicators_lock:
            return {idx_type: self.indicators.get(idx_type) for idx_type in indicator_types}

    def _execute_signal_strategy(
        self: "StrategyManager",
        key: str,
        required_indicators: list[IndexType],
        signal_logic: Callable[[dict[IndexType, Index | None]], Signal | None],
        verify_freshness: bool = True,
    ) -> None:
        """
        Generic signal generation loop that handles locking, timing, and callbacks.

        param key: str
            - Signal identifier for logging and timestamp tracking
        param required_indicators: list[IndexType]
            - List of indicator types needed for this signal
        param signal_logic: Callable
            - Function that takes indicators dict and returns Signal or None
        param verify_freshness: bool
            - Whether to verify indicator timestamps before processing
        """
        while True:
            indicators = self._get_indicators_safely(*required_indicators)

            # Verify all indicators are fresh if required
            should_process = True
            if verify_freshness:
                should_process = all(
                    self.__verify_index(ind) for ind in indicators.values() if ind
                )

            if should_process and self._should_generate_signal(key):
                signal = signal_logic(indicators)

                if signal:
                    self.push_signal(signal=signal, details=key)

                self.__update_signal_timestamp(key)

            time.sleep(self.SLEEP_INTERVAL)

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
        def golden_cross_logic(indicators: dict[IndexType, Index | None]) -> Signal | None:
            sma_data = indicators.get(IndexType.SMA)
            ema_data = indicators.get(IndexType.EMA)

            if not (sma_data and ema_data):
                return None

            ten_sec_sma: float | None = self._get_indicator_value(sma_data, 10)
            five_min_ema: float | None = self._get_indicator_value(ema_data, 300)

            if ten_sec_sma and five_min_ema and ten_sec_sma > five_min_ema:
                return StrategyManager.generate_signal(signal=TradeSignal.LONG_TERM_BUY)
            return None

        self._execute_signal_strategy(
            key="golden_cross",
            required_indicators=[IndexType.SMA, IndexType.EMA],
            signal_logic=golden_cross_logic,
            verify_freshness=True,
        )

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
        def death_cross_logic(indicators: dict[IndexType, Index | None]) -> Signal | None:
            sma_data = indicators.get(IndexType.SMA)
            ema_data = indicators.get(IndexType.EMA)
            
            if not (sma_data and ema_data):
                return None
            
            ten_sec_sma: float | None = self._get_indicator_value(sma_data, 10)
            five_min_ema: float | None = self._get_indicator_value(ema_data, 300)
            
            if ten_sec_sma and five_min_ema and ten_sec_sma < five_min_ema:
                return StrategyManager.generate_signal(signal=TradeSignal.LONG_TERM_SELL)
            return None
        
        self._execute_signal_strategy(
            key="death_cross",
            required_indicators=[IndexType.SMA, IndexType.EMA],
            signal_logic=death_cross_logic,
            verify_freshness=True,
        )

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
        def price_ma_logic(indicators: dict[IndexType, Index | None]) -> Signal | None:
            sma_data: Index | None = indicators.get(IndexType.SMA)
            current_price: float | None = indicators.get(IndexType.PRICE)
            
            if not (sma_data and current_price):
                return None
            
            sma_60 = self._get_indicator_value(sma_data, 60)
            
            if sma_60:
                if current_price > sma_60:
                    trading_logger.info(
                        f"{__name__} - Short Term Buy Signal has been generated!: Bullish Trend."
                    )
                    return StrategyManager.generate_signal(signal=TradeSignal.SHORT_TERM_BUY)
                elif current_price < sma_60:
                    trading_logger.info(
                        f"{__name__} - Short Term Sell Signal has been generated!: Bearish Trend."
                    )
                    return StrategyManager.generate_signal(signal=TradeSignal.SHORT_TERM_SELL)
            return None

        self._execute_signal_strategy(
            key="price_moving_average",
            required_indicators=[IndexType.SMA, IndexType.PRICE],
            signal_logic=price_ma_logic,
            verify_freshness=False,
        )

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
        def ema_sma_divergence_logic(indicators: dict[IndexType, Index | None]) -> Signal | None:
            sma_data: Index | None = indicators.get(IndexType.SMA)
            ema_data: Index | None = indicators.get(IndexType.EMA)
            
            if not (sma_data and ema_data):
                return None
            
            sma_60 = self._get_indicator_value(sma_data, 60)
            ema_60 = self._get_indicator_value(ema_data, 60)
            
            if sma_60 and ema_60:
                divergence: float = abs(sma_60 - ema_60)
                if divergence > threshold:
                    trading_logger.info(
                        f"{__name__} - Divergence Signal has been generated!: Potential Trend Change."
                    )
                    return StrategyManager.generate_signal(signal=TradeSignal.HOLD)
            return None

        self._execute_signal_strategy(
            key="ema_sma_divergence",
            required_indicators=[IndexType.SMA, IndexType.EMA],
            signal_logic=ema_sma_divergence_logic,
            verify_freshness=False,
        )

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
        def price_reversal_logic(indicators: dict[IndexType, Index | None]) -> Signal | None:
            sma_data: Index | None = indicators.get(IndexType.SMA)
            current_price: float | None = indicators.get(IndexType.PRICE)

            if not (sma_data and current_price):
                return None

            sma_60: float | None = self._get_indicator_value(sma_data, 60)

            if sma_60:
                if current_price > sma_60:
                    trading_logger.info(
                        f"{__name__} - Price Reversal Signal has been generated!: Bullish Reveral."
                    )
                    return StrategyManager.generate_signal(signal=TradeSignal.SHORT_TERM_BUY)
                elif current_price < sma_60:
                    trading_logger.info(
                        f"{__name__} - Price Reversal Signal has been generated!: Bearish Reveral."
                    )
                    return StrategyManager.generate_signal(signal=TradeSignal.SHORT_TERM_SELL)
            return None

        self._execute_signal_strategy(
            key="price_reversal",
            required_indicators=[IndexType.SMA, IndexType.PRICE],
            signal_logic=price_reversal_logic,
            verify_freshness=False,
        )
