from __future__ import annotations
from dataclasses import dataclass
from enum import IntFlag

from src.core.models.base import ImmutableModel


class OrderHistory:
    '''
    - Data structure to store the order history.

    - It should support:
        - search based on diffrent criteria
        - range search
    '''
    def __init__(
        self,
        max_size: int = 100,
    ) -> None:
        return


class Side(IntFlag):
    BUY = 1 << 0  # 0001
    SELL = 1 << 1  # 0010


@dataclass(frozen=True)
class Order(ImmutableModel):
    side: Side  # BUY or SELL
    type_str: str  # "BUY" or "SELL"
    leverage: int
    entry_price: float  # Entry price - current price
    tp_price: float  # Take Profit Price: + 20% for reverse ordering enabled broker
    sl_price: float  # Stop Loss Price: -20% for reverse ordering enblaed broker
    ticker: str
    ticker_size: float
    quote: str
    quote_size: float
    meta_data: dict | None  # to keep the metadata in the form of json.
