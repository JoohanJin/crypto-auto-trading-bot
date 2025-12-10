from dataclasses import dataclass
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
    BUY = 1  # 1
    SELL = 2  # 10


@dataclass
class Order:
    type: OrderType
    type_str: str
    leverage: int
    entry_price: float
    tp_price: float
    sl_price: float
    ticker: str
    ticker_size: float
    quote: str
    quote_size: float
    meta_data: dict | None  # to keep the metadata in the form of json.
