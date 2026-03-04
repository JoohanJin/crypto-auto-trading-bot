# STANDARD LIBRARY
from dataclasses import dataclass
from typing import Any

# CUSTOM LIBRARY
from src.core.models.index import IndexType
from src.core.models.signal import TradeSignal
from src.strategy.strategy_condition import StrategyCondition


@dataclass
class StrategyConfig:
    name: str
    enabled: bool
    indicators: list[IndexType]
    verify_freshness: bool
    conditions: list[StrategyCondition]
    signal_type: TradeSignal
    signal_window: int
    parameters: dict[str, Any] | None = None
    description: str | None = None
