# Standard Library
from dataclasses import dataclass

# Custom Library
from src.core.models.base import ImmutableModel
from src.core.models.trade import OrderType, TimeInForce, TradePair


@dataclass(frozen=True)
class ServiceDTO(ImmutableModel):
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
    price: float


@dataclass(frozen=True)
class FairPrice(ServiceDTO):
    ticker: TradePair
    fair_price: float


@dataclass(frozen=True)
class Kline(ServiceDTO):
    ticker: TradePair
    interval: str  # Or define enum for this?
    amount: float
    open_price: float
    close_price: float
    high_price: float
    low_price: float


@dataclass(frozen=True)
class OrderBook(ServiceDTO):
    ticker: TradePair
    asks: list
    bids: list


@dataclass(frozen=True)
class Position(ServiceDTO):
    id: int  # orderId
    ticker: TradePair  # symbol converted to TradePair
    status: str  # NEW, FILLED, CANCELED, etc.
    time_in_force: TimeInForce  # GTC, GTE_GTC, etc.
    order_type: OrderType  # MARKET, STOP_MARKET, TRAILING_STOP_MARKET, etc.
    side: str  # BUY or SELL
    position_side: str  # LONG, SHORT, or BOTH
    orig_qty: float  # Original quantity
    executed_qty: float  # Executed quantity
    avg_price: float  # Average execution price
    cum_quote: float  # Cumulative quote asset transacted quantity
    price: float = 0.0  # Limit price (0 for MARKET orders)
    stop_price: float = 0.0  # Stop price
    reduce_only: bool = False
    close_position: bool = False
    order_time: int = 0  # Order creation time
    update_time: int = 0  # Last update time
    client_order_id: str = ""  # Client order ID
    working_type: str = "CONTRACT_PRICE"  # CONTRACT_PRICE or MARK_PRICE
    price_match: str = "NONE"  # Price match mode
    self_trade_prevention_mode: str = "NONE"  # Self trading prevention mode
    good_till_date: int = 0  # GTD order pre-set auto-cancel time
    price_protect: bool = False  # Conditional order trigger protection
    activate_price: float = 0.0  # Activation price (TRAILING_STOP_MARKET only)
    price_rate: float = 0.0  # Callback rate (TRAILING_STOP_MARKET only)


@dataclass(frozen=True)
class AccountInformation(ServiceDTO):
    ticker: TradePair
