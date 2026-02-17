# STANDARD LIBRARY
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# CUSTOM LIBRARY
from src.core.models.index import IndexType
from src.core.models.signal import TradeSignal
from src.strategy.strategy_condition import StrategyCondition


@dataclass
class StrategyConfig:
    name: str
    enabled: bool
    indicators: List[IndexType]
    verify_freshness: bool
    conditions: List[StrategyCondition]
    signal_type: TradeSignal
    signal_window: int
    parameters: Optional[Dict[str, Any]] = None
    description: str | None = None
