from __future__ import annotations
from dataclasses import dataclass, replace
from enum import IntFlag


class TradeState(IntFlag):
    '''
    - Data structure used in trade_manager (ENUM)
    '''
    HOLD = 1
    NEW_BUY = 2
    NEW_SELL = 4
    REVERSE_BUY = 8
    REVERSE_SELL = 16


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

    def __repr__(self) -> str:
        return f"TradePair object - ticker: {self.ticker} - quote: {self.quote}"
