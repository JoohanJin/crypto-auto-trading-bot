# STANDARD LIBRARY
import threading
from pathlib import Path
from typing import Any, Callable, Dict
import time

# CUSTOM LIBRARY
from src.infrastructure.logging.set_logger import get_logger, get_adapter
from src.core.models.index import IndexType, Index
from src.core.models.signal import TradeSignal, Signal
from src.strategy import (
    StrategyExecutor,
    StrategyFactory,
    StrategyFetcher,
    StrategyConfig,
    StrategyCondition,
)

logger = get_logger(__name__)


class StrategyManager:
    SLEEP_INTERVAL: float = 1.5
    STRATEGY_CONFIG_PATH: Path = Path(__file__).resolve().parent.parent / "config" / "strategies.json"

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
                logger.info(f"Thread '{thread.name}' (ID: {thread.ident}) has started")
            except RuntimeError as e:
                logger.critical(f"Failed to start thread '{thread.name}': {str(e)}")
                raise RuntimeError(f"Failed to start thread '{thread.name}': {str(e)}")
            except Exception as e:
                logger.critical(f"Unexpected error starting thread: '{thread.name}': {str(e)}")
                raise Exception(
                    f"Unexpected error starting thread: '{thread.name}': {str(e)}"
                )
        return

    def __init__(
        self,
        indicators: dict[IndexType, Index | float | None],
        indicators_lock: threading.Lock,
        push_signal_callback: Callable[[Signal], None],
        signal_window: int = 5_000,
        name: str | None = None,
    ) -> None:
        self.name: str = name if name else "STRATEGY_MANAGER"
        self.logger = get_adapter(logger, f"{self.__class__.__name__}_{self.name}")
        self.trading_logger = get_adapter(get_logger(__name__, "trading"), f"{self.__class__.__name__}_{self.name}")

        # shared data structure to store Timestamp of the previoius invokation of each signal.
        self.signal_timestamps: dict[str, int] = dict()
        self.signal_timestamps_lock: threading.Lock = threading.Lock()
        self.signal_window: int = signal_window
        self.threads: list[threading.Thread] = []

        self.indicators: dict[IndexType, Index | float | None] = indicators
        self.indicators_lock: threading.Lock = indicators_lock
        self._push_signal_callback: Callable[[Signal], None] = push_signal_callback
        self.strategy_executor: StrategyExecutor | None = None
        self.strategy_configs: list[StrategyConfig] = []

        self.start()
        return

    def start(self) -> None:
        # if this is the thread-based class
        self._load_strategies()
        self.__init_threads()
        StrategyManager.start_threads(self.threads)

    def push_signal(self, signal: Signal, details: str) -> None:
        try:
            self._push_signal_callback(signal)
            self.trading_logger.info(f"{details} Signal has been generated.")
        except Exception as e:
            self.logger.critical(f"Cannot push signal '{signal.signal.name}': {str(e)}")

    def _load_strategies(self) -> None:
        fetcher = StrategyFetcher(self.STRATEGY_CONFIG_PATH)
        raw_config = fetcher.load_strategies()

        # Align sleep interval with config if provided
        global_settings: Dict[str, Any] = raw_config.get("global_settings", {})
        self.SLEEP_INTERVAL = global_settings.get("sleep_interval", self.SLEEP_INTERVAL)

        factory = StrategyFactory()
        self.strategy_configs = factory.build_all(raw_config)

        self.strategy_executor = StrategyExecutor(
            push_signal=self.push_signal,
            get_indicators=lambda indicator_types: self._get_indicators_safely(*indicator_types),
            should_generate=self._should_generate_signal,
            update_timestamp=self.__update_signal_timestamp,
            verify_index=self.__verify_index,
            sleep_interval=self.SLEEP_INTERVAL,
        )

    def __init_threads(self) -> None:
        """
        Initialize strategy execution threads based on loaded configurations.
        """
        if not self.strategy_executor:
            self.logger.critical("StrategyExecutor is not initialized.")
            return

        for strategy in self.strategy_configs:
            logic = self._build_strategy_logic(strategy)
            name = f"{strategy.name}_signal_generator"
            thread = threading.Thread(
                name=name,
                target=self.strategy_executor.execute,
                args=(strategy, logic),
                daemon=True,
            )
            self.threads.append(thread)
            self.logger.info(f"Thread for {name} has been set up!")

    def __verify_index(
        self,
        index: Index,
        time_window: int = 5_000,
    ) -> bool:
        if (StrategyManager.generate_timestamp() - index.timestamp < time_window):
            return True
        else:
            return False

    def __extract_data(
        self,
        index: Index,
    ) -> dict[int, float] | None:
        if index:
            return index.data
        else:
            return None

    def _get_indicator_value(
        self,
        indicator: Index | None,
        window: int,
    ) -> float | None:
        data = self.__extract_data(indicator) if indicator else None
        return data.get(window) if data else None

    def _resolve_indicator_value(
        self,
        indicators: dict[IndexType, Index | float | None],
        indicator_name: str,
        window: int | None = None,
    ) -> float | None:
        """
        Resolve indicator value from the shared indicator map, handling both Index objects and raw floats.
        """
        if not indicator_name:
            return None

        try:
            idx_type = IndexType[indicator_name]
        except KeyError:
            self.logger.critical(f"Unknown indicator '{indicator_name}' in strategy config.")
            return None

        indicator_obj = indicators.get(idx_type)
        if indicator_obj is None:
            return None

        if isinstance(indicator_obj, Index):
            if window is None:
                return None
            return self._get_indicator_value(indicator_obj, window)

        # For raw numeric indicators (e.g., PRICE if stored as float)
        return indicator_obj if window is None else indicator_obj

    def _compare(self, left: float, right: float, operator: str) -> bool:
        if operator == ">":
            return left > right
        if operator == "<":
            return left < right
        if operator == ">=":
            return left >= right
        if operator == "<=":
            return left <= right
        if operator == "==":
            return left == right
        return False

    def _evaluate_condition(
        self,
        condition: StrategyCondition,
        indicators: dict[IndexType, Index | float | None],
        strategy: StrategyConfig,
    ) -> TradeSignal | None:
        payload = condition.payload

        if condition.type == "comparison":
            left_cfg = payload.get("left", {})
            right_cfg = payload.get("right", {})
            operator = payload.get("operator", "")

            left_val = self._resolve_indicator_value(indicators, left_cfg.get("indicator", ""), left_cfg.get("window"))
            right_val = self._resolve_indicator_value(indicators, right_cfg.get("indicator", ""), right_cfg.get("window"))

            if left_val is None or right_val is None:
                return None

            if self._compare(left_val, right_val, operator):
                return strategy.signal_type

        elif condition.type == "price_comparison":
            price_indicator = payload.get("price_indicator", "")
            compare_to = payload.get("compare_to", {})
            price_val = self._resolve_indicator_value(indicators, price_indicator)
            compare_val = self._resolve_indicator_value(
                indicators,
                compare_to.get("indicator", ""),
                compare_to.get("window"),
            )

            if price_val is None or compare_val is None:
                return None

            buy_operator = payload.get("buy_operator", "")
            sell_operator = payload.get("sell_operator", "")

            if buy_operator and self._compare(price_val, compare_val, buy_operator):
                buy_signal = payload.get("buy_signal")
                return TradeSignal[buy_signal] if buy_signal else None
            if sell_operator and self._compare(price_val, compare_val, sell_operator):
                sell_signal = payload.get("sell_signal")
                return TradeSignal[sell_signal] if sell_signal else None

        elif condition.type == "divergence":
            left_cfg = payload.get("left", {})
            right_cfg = payload.get("right", {})
            operator = payload.get("operator", "")

            left_val = self._resolve_indicator_value(indicators, left_cfg.get("indicator", ""), left_cfg.get("window"))
            right_val = self._resolve_indicator_value(indicators, right_cfg.get("indicator", ""), right_cfg.get("window"))

            if left_val is None or right_val is None:
                return None

            threshold = payload.get("threshold")
            if threshold is None and strategy.parameters:
                threshold = strategy.parameters.get("threshold")
            if threshold is None:
                return None

            if operator == "abs_difference" and abs(left_val - right_val) > threshold:
                return strategy.signal_type

        return None

    def _build_strategy_logic(
        self,
        strategy: StrategyConfig,
    ) -> Callable[[dict[IndexType, Index | float | None], StrategyConfig], TradeSignal | None]:
        def logic(indicators: dict[IndexType, Index | float | None], cfg: StrategyConfig) -> TradeSignal | None:
            for condition in cfg.conditions:
                signal = self._evaluate_condition(condition, indicators, cfg)
                if signal:
                    return signal
            return None

        return logic

    def __update_signal_timestamp(
        self,
        key: str,
    ) -> None:
        with self.signal_timestamps_lock:
            self.signal_timestamps[key] = StrategyManager.generate_timestamp()
        return

    def __get_signal_timestamp(
        self,
        key: str,
    ) -> int:
        with self.signal_timestamps_lock:
            return self.signal_timestamps.get(key, 0)

    def _should_generate_signal(
        self,
        key: str,
        signal_window: int | None = None,
    ) -> bool:
        """
        Check if enough time has passed since the last signal generation.

        param key: str
            - The signal identifier key

        return bool
            - True if signal should be generated, False otherwise
        """
        prev_timestamp: int = self.__get_signal_timestamp(key)
        window = signal_window if signal_window is not None else self.signal_window
        return StrategyManager.generate_timestamp() - prev_timestamp > window

    def _get_indicators_safely(
        self,
        *indicator_types: IndexType,
    ) -> dict[IndexType, Index | float | None]:
        """
        Thread-safe retrieval of multiple indicators.

        param indicator_types: IndexType
            - Variable number of indicator types to retrieve

        return dict[IndexType, Index | None]
            - Dictionary mapping indicator types to their Index objects
        """
        with self.indicators_lock:
            return {idx_type: self.indicators.get(idx_type) for idx_type in indicator_types}
