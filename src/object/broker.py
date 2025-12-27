from __future__ import annotations
import time

from binance.base_sdk import FutureBase
from object.trade import TradePair


class Broker:
    '''
    - Wrapper class for the Future Manager:
        - MexC
        - Binance
    '''
    @staticmethod
    def generate_timestamp() -> int:
        return int(time.time() * 1_000)

    def __init__(
        self,
        broker_id: str,
        broker: FutureBase,
        enabled: bool,
        priority: int,
        max_leverage: int = 20,
        supported_pairs: set[TradePair] = None,
    ) -> None:
        self.broker_id: str  # Identifier
        self.broker: FutureBase  # Avaiable Broker
        self.enabled: bool = enabled
        self.priority: int = priority
        self.max_leverage: int = 20
        self.supported_pairs: set[TradePair] = supported_pairs

        return

    def get_ticker_amt(
        self,
        trade_pair: TradePair,
    ) -> float | None:
        return None

    def get_quote_amt(
        self,
        trade_pair: TradePair,
    ) -> float | None:
        return None
