from dataclasses import dataclass

from src.manager.trade_manager import TradePair


@dataclass
class Price:
    timestamp: int
    trading_pair: TradePair
    price: float
