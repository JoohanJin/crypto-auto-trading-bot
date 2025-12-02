from dataclasses import dataclass

from object.trade import TradePair


@dataclass
class Price:
    timestamp: int
    trading_pair: TradePair
    price: float
