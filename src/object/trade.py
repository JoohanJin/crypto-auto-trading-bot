from __future__ import annotations
from dataclasses import dataclass, replace
from enum import IntFlag


class TradeSignal(IntFlag):
    '''
    - Data structure used in trade_manager (ENUM)
    '''
    HOLD = 1
    NEW_BUY = 2
    NEW_SELL = 4
    REVERSE_BUY = 8
    REVERSE_SELL = 16


class TrendState(IntFlag):
    FLAT = 1  # 1
    STRONG_BULLISH = 2  # 10
    BULLISH = 4  # 100
    BEARISH = 8  # 1000
    STRONG_BEARISH = 16   # 1_0000


@dataclass
class ScoreMetrics:
    timestamp: int
    current_score: float
    trend: TrendState
    velocity: float
    acceleration: float
    volatility: float
    confidence: float


@dataclass
class TradePair:
    '''
    - Custom Data Structure with ticker and quote
        - Ticker: BTC by default
        - Quote: USDT by default (USDC in the future)
    '''
    ticker: str  # = "BTC"
    quote: str  # = "USDT"

    def copy(self) -> TradePair:
        return replace(self)


class ScoreHistory:
    '''
    - Data structure to store the score history.
    - Dequeue?
    - Tree? B+ ? -> But BST is also fine I think...? hmmm
    '''
    def __init__(
        self: "ScoreHistory",
        max_size: int = 100,
    ) -> None:
        # dict[id, pointer or reference] + linked list
        # consider heap or dequeue
        return

    def add(self,) -> None:
        return

    def get_recent(self, n: int):
        return

    def get_scores_since(self, timestamp: int):
        return

    def clear(self,) -> None:
        return
