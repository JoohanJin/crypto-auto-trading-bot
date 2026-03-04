# STANDARD LIBRARY
import copy
import time
from collections.abc import Callable

from src.core.models.index import Index, IndexType
from src.core.models.signal import Signal, TradeSignal

# CUSTOM LIBRARY
from src.infrastructure.logging.set_logger import get_adapter, get_logger
from src.strategy.strategy_config import StrategyConfig


logger = get_logger(__name__)


class StrategyExecutor:
    """
    Executes a StrategyConfig by delegating indicator access and signal push to StrategyManager.
    """

    def __init__(
        self,
        push_signal: Callable[[Signal, str], None],
        get_indicators: Callable[
            [list[IndexType]], dict[IndexType, Index | float | None]
        ],
        should_generate: Callable[[str, int], bool],
        update_timestamp: Callable[[str], None],
        verify_index: Callable[[Index, int], bool],
        sleep_interval: float,
        name: str | None = None,
    ) -> None:
        self.name: str = name if name else "STRATEGY_EXECUTOR"
        self.trading_logger = get_adapter(
            get_logger(__name__, "trading"), f"{self.__class__.__name__}_{self.name}"
        )

        self._push_signal: Callable = push_signal
        self._get_indicators: Callable = get_indicators
        self._should_generate: Callable = should_generate
        self._update_timestamp: Callable = update_timestamp
        self._verify_index: Callable = verify_index
        self._sleep_interval: Callable = sleep_interval

    def _emit_signal(self, signal_type: TradeSignal, details: str) -> None:
        self._push_signal(Signal(signal=signal_type), details)

    def execute(
        self,
        strategy: StrategyConfig,
        logic: Callable[
            [
                dict[IndexType, Index | float | None],
                dict[IndexType, Index | float | None] | None,
                StrategyConfig,
            ],
            TradeSignal | None,
        ],
    ) -> None:
        """
        Generic execution loop that can be launched in a thread.
        Maintains 'previous_indicators' state for crossover detection.
        """
        previous_indicators: dict[IndexType, Index | float | None] | None = None

        while True:
            indicators = self._get_indicators(strategy.indicators)
            should_process = True
            if strategy.verify_freshness:
                should_process = all(
                    self._verify_index(ind, strategy.signal_window)
                    for ind in indicators.values()
                    if ind
                )

            if should_process and self._should_generate(
                strategy.name, strategy.signal_window
            ):
                # Pass both current and previous indicators to logic
                signal_type = logic(indicators, previous_indicators, strategy)
                if signal_type:
                    self._emit_signal(signal_type, strategy.name)
                self._update_timestamp(strategy.name)

            # Update previous_indicators for the next iteration.
            # Deep copy is essential because 'indicators' contains mutable Index objects (with nested dicts)
            # that might be updated in-place by the data pipeline before the next loop.
            if indicators:
                previous_indicators = copy.deepcopy(indicators)

            time.sleep(self._sleep_interval)
