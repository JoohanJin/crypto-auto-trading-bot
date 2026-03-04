# Standard Library
from dataclasses import dataclass, field
from enum import IntFlag

from src.core.models.base import ImmutableModel


class TradeSignal(IntFlag):
    # state management using the bit manipulation.
    SHORT_TERM_BUY = 1 << 0  # 0001
    LONG_TERM_BUY = 1 << 1  # 0010
    SHORT_TERM_SELL = 1 << 2  # 0010
    LONG_TERM_SELL = 1 << 3  # 0100
    HOLD = 1 << 4  # 1000


@dataclass(frozen=True)
class Signal(ImmutableModel):
    signal: TradeSignal
    timestamp: int = field(default_factory=lambda: Signal.generate_timestamp())
