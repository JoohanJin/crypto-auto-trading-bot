from __future__ import annotations
from dataclasses import dataclass
from enum import IntFlag

from src.core.models.base import ImmutableModel


class TradeState(IntFlag):
    '''
    - Data structure used in trade_manager (ENUM)
    '''
    HOLD = 1 << 0  # 1
    NEW_BUY = 1 << 1  # 2
    NEW_SELL = 1 << 2  # 4
    REVERSE_BUY = 1 << 3  # 8
    REVERSE_SELL = 1 << 4  # 16


class TimeInForce(IntFlag):
    GTC = 1 << 0  # Good Til Canceled -> until fully fulfilled or manually cancel it.
    FOK = 1 << 1  # Fill-Or-Kill -> the order must be executed immedately, otherwise be canceled -> no partially filled
    IOC = 1 << 2  # Immediate or Cancel -> the order must be executed immedately, but can be partially filled.


class OrderType(IntFlag):
    LIMIT_ORDER = 1 << 0
    MARKET_ORDER = 1 << 1
    STOP_LIMIT_ORDER = 1 << 2
    STOP_MARKET_ORDER = 1 << 3
    TRAILING_STOP_ORDER = 1 << 4
    POST_ONLY_ORDER = 1 << 5
    LIMIT_TP_SL_ORDER = 1 << 6
    REVERSE_ORDER = 1 << 7
    SCALED_ORDER = 1 << 8
    CONDITIONAL_ORDER = 1 << 9
    TWAP = 1 << 10


@dataclass(frozen=True)
class TradePair(ImmutableModel):
    '''
    - Custom Data Structure with ticker and quote
        - Ticker: BTC by default
        - Quote: USDT by default (USDC in the future)
    '''
    ticker: str  # = "BTC"
    quote: str  # = "USDT"


if __name__ == "__main__":
    a = TradePair("BTC", "USDT")
