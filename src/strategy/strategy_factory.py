# STANDARD LIBRARY
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

# CUSTOM LIBRARY
from src.core.models.index import IndexType
from src.core.models.signal import TradeSignal


@dataclass
class StrategyCondition:
    type: str
    payload: Dict[str, Any]


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


class StrategyFactory:
    """
    Turns raw config dicts into typed StrategyConfig objects.
    """

    @staticmethod
    def _parse_indicator(indicator: str) -> IndexType:
        return IndexType[indicator]

    @staticmethod
    def _parse_signal(signal: str) -> TradeSignal:
        return TradeSignal[signal]

    def build(self, raw_strategy: Dict[str, Any]) -> StrategyConfig:
        indicators = [self._parse_indicator(ind) for ind in raw_strategy.get("indicators", [])]
        conditions = [
            StrategyCondition(type=cond.get("type", ""), payload=cond)  # payload kept flexible for now
            for cond in raw_strategy.get("conditions", [])
        ]

        params = raw_strategy.get("parameters") or None
        return StrategyConfig(
            name=raw_strategy.get("name", ""),
            enabled=raw_strategy.get("enabled", False),
            indicators=indicators,
            verify_freshness=raw_strategy.get("verify_freshness", True),
            conditions=conditions,
            signal_type=self._parse_signal(raw_strategy.get("signal_type", "HOLD")),
            signal_window=raw_strategy.get("signal_window", 5_000),
            parameters=params,
            description=raw_strategy.get("description"),
        )

    def build_all(self, raw_config: Dict[str, Any]) -> List[StrategyConfig]:
        return [
            self.build(strategy)
            for strategy in raw_config.get("strategies", [])
            if strategy.get("enabled", False)
        ]
