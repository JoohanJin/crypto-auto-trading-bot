from dataclasses import dataclass

from src.core.models.trade import TradePair


@dataclass
class Price:
    timestamp: int
    trading_pair: TradePair
    price: float
