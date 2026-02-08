# Standard Library
from dataclasses import dataclass

# Custom Library
from src.core.models.trade import TradePair


@dataclass(frozen=True)
class ServiceDTO:
    timestamp: int
    source: str


@dataclass(frozen=True)
class Ping(ServiceDTO):
    success: bool


@dataclass(frozen=True)
class FundingRate(ServiceDTO):
    ticker: TradePair


@dataclass(frozen=True)
class Ticker(ServiceDTO):
    ticker: TradePair
    last_price: float

    def __repr__(self) -> str:
        return f"Ticker Object at timestamp of {self.timestamp} for {self.ticker}"


@dataclass(frozen=True)
class Kline(ServiceDTO):
    ticker: TradePair
    interval: str  # Or define enum for this?
    amount: float
    open_price: float
    close_price: float
    high_price: float
    low_price: float

    def __repr__(self) -> str:
        return f"Kline Object at timestamp of {self.timestamp} for {self.ticker}"


@dataclass(frozen=True)
class OrderBook(ServiceDTO):
    ticker: TradePair
    asks: list
    bids: list

    def __repr__(self) -> str:
        return f"Depth Object at timestamp of {self.timestamp} for {self.ticker}"
