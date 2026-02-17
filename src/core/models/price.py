from dataclasses import dataclass

from src.core.models.base import MutableModel
from src.core.models.trade import TradePair


@dataclass
class Price(MutableModel):
    timestamp: int
    trading_pair: TradePair
    price: float
