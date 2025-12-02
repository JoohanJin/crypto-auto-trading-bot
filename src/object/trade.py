from dataclasses import dataclass
from enum import IntFlag


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
        # heap or dequeue?
        return

    def add(self) -> None:
        return

    def get_recent(n: int):
        return

    def get_scores_since(timestamp: int):
        return

    def clear() -> None:
        return
