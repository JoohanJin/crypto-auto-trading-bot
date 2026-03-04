from __future__ import annotations

from dataclasses import dataclass
from enum import IntFlag

from src.core.models.base import Side, TradePair


class TradeState(IntFlag):
    """
    - Data structure used in trade_manager (ENUM)
    """

    HOLD = 1 << 0  # 1
    NEW_BUY = 1 << 1  # 2
    NEW_SELL = 1 << 2  # 4
    REVERSE_BUY = 1 << 3  # 8
    REVERSE_SELL = 1 << 4  # 16
    EXIT = 1 << 5  # 32


class TimeInForce(IntFlag):
    GTC = 1 << 0  # Good Til Canceled -> until fully fulfilled or manually cancel it.
    FOK = (
        1 << 1
    )  # Fill-Or-Kill -> the order must be executed immedately, otherwise be canceled -> no partially filled
    IOC = (
        1 << 2
    )  # Immediate or Cancel -> the order must be executed immedately, but can be partially filled.


class PositionType(IntFlag):
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


@dataclass
class PositionState:
    """
    Represents the current position held by the TradeManager.

    Separates "position" (what we actually hold) from "order" (what we send to the exchange).
    This prevents size explosion during REVERSE operations:
        - Order size for REVERSE = position_size (close) + base_size (new) = 2x
        - But the actual new position is still base_size, not 2x.

    Fields:
        side: int
            - Side.BUY (1, long) or Side.SELL (2, short). Uses int to avoid circular import with order.py.
        ticker_size: float
            - The actual position quantity in ticker (e.g., BTC). Always base size.
        quote_size: float
            - The actual position value in quote (e.g., USDT). Always base size.
        entry_price: float
            - The price at which the position was entered.
        timestamp: int
            - The timestamp (ms) when the position was opened.
    """

    side: int | Side  # Side.BUY or Side.SELL (IntFlag, int-compatible)
    ticker_size: float
    quote_size: float
    entry_price: float
    timestamp: int

    def copy(self) -> PositionState:
        return PositionState(
            side=self.side,
            ticker_size=self.ticker_size,
            quote_size=self.quote_size,
            entry_price=self.entry_price,
            timestamp=self.timestamp,
        )


if __name__ == "__main__":
    a = TradePair("BTC", "USDT")
    print(a)
    print(TradeState["NEW_BUY"])
