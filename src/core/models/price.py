from dataclasses import dataclass

from core.models.trade import TradePair


@dataclass
class Price:
    timestamp: int
    trading_pair: TradePair
    price: float
