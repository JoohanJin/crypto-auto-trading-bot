# Standard Library
from dataclasses import dataclass

# Custom Library
from src.core.models.trade import TradePair


@dataclass(frozen=True)
class WebSocketDTO:
    ticker: TradePair
    timestamp: int


@dataclass(frozen=True)
class Ticker(WebSocketDTO):
    last_price: float

    def __repr__(self) -> str:
        return f"Ticker Object at timestamp of {self.timestamp} for {self.ticker}"


@dataclass(frozen=True)
class Kline(WebSocketDTO):
    interval: str  # Or define enum for this?
    amount: float
    open_price: float
    close_price: float
    high_price: float
    low_price: float

    def __repr__(self) -> str:
        return f"Kline Object at timestamp of {self.timestamp} for {self.ticker}"


@dataclass(frozen=True)
class Depth(WebSocketDTO):
    asks: list
    bids: list

    def __repr__(self) -> str:
        return f"Depth Object at timestamp of {self.timestamp} for {self.ticker}"
