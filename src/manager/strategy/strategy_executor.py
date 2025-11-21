# STANDARD LIBRARY
import time
from typing import Callable, Dict

# CUSTOM LIBRARY
from logger.set_logger import trading_logger
from object.constants import IndexType
from object.indexes import Index
from object.signal import Signal
from object.signal import TradeSignal
from manager.strategy.strategy_factory import StrategyConfig


class StrategyExecutor:
    """
    Executes a StrategyConfig by delegating indicator access and signal push to StrategyManager.
    """

    def __init__(
        self,
        push_signal: Callable[[Signal, str], None],
        get_indicators: Callable[[list[IndexType]], dict[IndexType, Index | float | None]],
        should_generate: Callable[[str, int], bool],
        update_timestamp: Callable[[str], None],
        verify_index: Callable[[Index, int], bool],
        sleep_interval: float,
    ) -> None:
        self._push_signal = push_signal
        self._get_indicators = get_indicators
        self._should_generate = should_generate
        self._update_timestamp = update_timestamp
        self._verify_index = verify_index
        self._sleep_interval = sleep_interval

    def _emit_signal(self, signal_type: TradeSignal, details: str) -> None:
        self._push_signal(Signal(signal=signal_type), details)

    def execute(
        self,
        strategy: StrategyConfig,
        logic: Callable[[Dict[IndexType, Index | float | None], StrategyConfig], TradeSignal | None],
    ) -> None:
        """
        Generic execution loop that can be launched in a thread.
        """
        while True:
            indicators = self._get_indicators(strategy.indicators)

            should_process = True
            if strategy.verify_freshness:
                should_process = all(
                    self._verify_index(ind, strategy.signal_window) for ind in indicators.values() if ind
                )

            if should_process and self._should_generate(strategy.name, strategy.signal_window):
                signal_type = logic(indicators, strategy)
                if signal_type:
                    trading_logger.info(f"{__name__} - {strategy.name} Signal generated.")
                    self._emit_signal(signal_type, strategy.name)
                self._update_timestamp(strategy.name)

            time.sleep(self._sleep_interval)
