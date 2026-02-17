# Standard Library
import time
from abc import ABC, abstractmethod

# Logger
from src.infrastructure.logging.set_logger import get_logger, get_adapter

# Custom Library
from src.core.models.trade import TradePair


logger = get_logger(__name__)


class HttpClient(ABC):
    @classmethod
    @abstractmethod
    def _parse_trade_pair(
        cls,
        trade_pair: TradePair,
    ) -> str:
        """
        Convert a TradePair object to the exchange-specific symbol format.

        Args:
            trade_pair: TradePair object (ticker + quote)

        Returns:
            Symbol string in exchange format (e.g., "BTCUSDT" or "BTC_USDT")
        """
        return

    def generate_timestamp(self) -> int:
        return int(time.time() * 1_000)

    def __init__(
        self,
        name: str | None = None,
    ) -> None:
        self.name: str = name or "HTTP_CLIENT"
        self.logger = get_adapter(logger, f"{self.__class__.__name__}_{self.name}")
        
        self.logger.info(f"[SERVICE_INIT] {self.name} initialized")

        return

    @abstractmethod
    def ping(self):
        return

    @abstractmethod
    def get_order_book(self):
        return

    @abstractmethod
    def get_kline(self):
        return

    @abstractmethod
    def get_ticker(self):
        return

    @abstractmethod
    def get_funding_rate_history(self):
        return

    @abstractmethod
    def get_account_balance(self):
        return

    @abstractmethod
    def get_positions(self):
        return

    @abstractmethod
    def get_open_orders(self):
        return

    @abstractmethod
    def place_order(self):
        return
