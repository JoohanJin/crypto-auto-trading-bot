from __future__ import annotations
from dataclasses import dataclass, replace
from enum import IntFlag


class OrderHistory:
    '''
    - Data structure to store the order history.

    - It should support:
        - search based on diffrent criteria
        - range search
    '''
    def __init__(
        self: "OrderHistory",
        max_size: int = 100,
    ) -> None:
        return


class OrderType(IntFlag):
    BUY = 1  # 0001
    SELL = 2  # 0010


@dataclass
class Order:
    type: OrderType  # BUY or SELL
    type_str: str  # "BUY" or "SELL"
    leverage: int
    entry_price: float  # Entry price - current price
    tp_price: float  # Take Profit Price: + 20% for reverse ordering enabled borker
    sl_price: float  # Stop Loss Price: -20% for reverse ordering enblaed broker
    ticker: str
    ticker_size: float
    quote: str
    quote_size: float
    meta_data: dict | None  # to keep the metadata in the form of json.

    def copy(self) -> Order:
        return replace(self)
