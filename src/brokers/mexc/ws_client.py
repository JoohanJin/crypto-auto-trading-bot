# Standard Library
import time
from collections.abc import Callable
from typing import Literal

# WebSocket
from src.brokers.base.ws_client import WebSocketClient
from src.brokers.mexc.ws_gateway import MexcWebSocket

# Models
from src.core.models.service_dto import OrderBook, Ticker
from src.core.models.trade import TradePair

# Logger
from src.infrastructure.logging.set_logger import get_adapter, get_logger


logger = get_logger(__name__)


class MexcWebSocketClient(WebSocketClient):
    def generate_timestamp(self) -> int:
        return int(time.time() * 1_000)

    def __init__(
        self,
        name: str | None = None,
        url: str = "wss://contract.mexc.com/edge",
        api_key: str | None = None,
        secret_key: str | None = None,
        ping_interval: int | None = 20,  # as it is recommended
        default_callback: Callable | None = None,
    ) -> None:
        super().__init__(
            name = name if name else "MEXC_FUTURE_WEBSOCKET_CLIENT"
        )
        self.logger = get_adapter(logger, f"{self.__class__.__name__}_{self.name}")

        self.ws: MexcWebSocket = MexcWebSocket(
            url=url,
            name=f"{self.name}_WEBSOCKET",
            api_key=api_key,
            secret_key=secret_key,
            ping_interval=ping_interval,
            default_callback=default_callback,
        )

    def start(self) -> None:
        try:
            self.ws.start()
            self.logger.info(
                f"[WS_OPEN] MexC | URL: {self.ws.url} | Status: opened"
            )
        except Exception as e:
            self.logger.info(
                f"[WS_OPEN] MexC | Error: {type(e).__name__}: {e!s}"
            )

    @classmethod
    def _parse_trade_pair(
        self,
        trade_pair: TradePair,
    ) -> str:
        if isinstance(trade_pair, TradePair):
            return f"{trade_pair.ticker.upper()}_{trade_pair.quote.upper()}"
        return "BTC_USDT"

    def _construct_trade_pair(
        self,
        symbol: str,
    ) -> TradePair:
        trade_pair: list[str] = symbol.split("_") if "_" in symbol else ["BTC", "USDT"]
        return TradePair(ticker=trade_pair[0], quote=trade_pair[1])

    def _generate_param(
        self,
        trade_pair: TradePair | None = None,
        param: dict | None = None,
    ) -> dict:
        symbol: str = self._parse_trade_pair(trade_pair)

        res = dict(param) if param else {}
        res['symbol'] = symbol
        return res

    """
    - Public Endpoint
        - Tickers
        - Ticker
        - Transaction
        - Depth
        - k-line
        - Funding Rate
        - Index Price
        - Fair Price
    """
    def tickers(
        self,
        callback: Callable,
    ) -> None:
        """
        - Get the latest transaction price, buy-price, sell-price and 24 transaction volume
        - of all the perpetual contracts on the platform without login.
        - Send once a second after subscribing
        """
        topic = "tickers"
        self.ws.subscribe(topic = topic, callback = callback, param = {})

    # Essential Function
    def ticker(
        self,
        callback: Callable,
        trade_pair: TradePair | None = None,
        param: dict | None = None,
    ) -> None:
        """
        - Get the latest transaction price, buy price, sell price and 24 transaction volume
        - of a contract, send the transaction data without users' login.
        - Send once a second after subscription.
        """
        def ticker_wrapper(msg: dict) -> None:
            data = msg.get("data", {})

            # Parse symbol string back to TradePair (e.g., "BTC_USDT" -> "BTC", "USDT")
            trade_pair: TradePair = self._construct_trade_pair(msg.get("symbol", data.get("symbol", "")))

            ticker_dto: Ticker = Ticker(
                ticker=trade_pair,
                timestamp=data.get("timestamp", self.generate_timestamp()),
                source="MEXC",
                price=float(data.get("lastPrice", 0.0))
            )
            callback(ticker_dto)

        topic: str = "ticker"
        self.ws.subscribe(
            topic = topic,
            callback = ticker_wrapper,
            param = self._generate_param(
                trade_pair=trade_pair,
                param=param,
            ),
        )

    def deal(
        self,
        callback: Callable,
        trade_pair: TradePair | None = None,
        param: dict | None = None,
    ) -> None:
        """
        - Access to the latest data without login, and keep updating
        """
        topic = "deal"
        self.ws.subscribe(
            topic=topic,
            callback=callback,
            param=self._generate_param(
                trade_pair=trade_pair,
                param=param,
            ),
        )

    def order_book(
        self,
        callback: Callable,
        trade_pair: TradePair | None = None,
        param: dict | None = None,
    ):
        def order_book_wrapper(msg: dict) -> None:
            data: dict = msg.get("data", {})
            ticker_part, quote_part = self._construct_trade_pair(msg.get("symbol", data.get("symbol", "")))

            depth_dto: OrderBook = OrderBook(
                ticker=TradePair(ticker=ticker_part, quote=quote_part),
                timestamp=data.get("timestamp", self.generate_timestamp()),
                source="MEXC",
                asks = [],
                bids = [],
            )
            callback(depth_dto)

        topic = "depth"
        self.ws.subscribe(
            topic=topic,
            callback=order_book_wrapper,
            param=self._generate_param(
                trade_pair=trade_pair,
                param=param,
            ),
        )

    def kline(
        self,
        callback: Callable,
        trade_pair: TradePair | None = None,
        interval: Literal["Min1"] | Literal["Min5"] | Literal["Min15"] | Literal["Min30"] | Literal["Min60"] | Literal["Hour4"] | Literal["Hour8"] | Literal["Day1"] | Literal["Week1"] | Literal["Month1"] | None = "Min1",
    ):
        """
        - Get the k-line data of the contract and keep updating.
        - subscribe, unsubscribe, example is shown on the right.
        - interval optional parameters:
            - Min1
            - Min5
            - Min15
            - Min30
            - Min60
            - Hour4
            - Hour8
            - Day1
            - Week1
            - Month1
        """
        symbol: str = self._parse_trade_pair(trade_pair)
        param = {"symbol": symbol, "interval": interval}
        topic = "kline"
        self.ws.subscribe(topic=topic, callback=callback, param=param)

    def funding_rate(
        self,
        callback: Callable,
        trade_pair: TradePair | None = None,
        param: dict | None = None,
    ) -> None:
        """
        - Get the contract funding rate and keep updating
        """
        topic: str = "funding.rate"
        self.ws.subscribe(
            topic=topic,
            callback=callback,
            param=self._generate_param(
                trade_pair=trade_pair,
                param=param,
            ),
        )

    def index_price(
        self,
        callback: Callable,
        trade_pair: TradePair | None = None,
        param: dict | None = None,
    ) -> None:
        """
        - Get the index price and will keep updating if there is any changes
        """
        topic = "index.price"
        self.ws.subscribe(
            topic=topic,
            callback=callback,
            param=self._generate_param(
                trade_pair=trade_pair,
                param=param,
            ),
        )

    def fair_price(
        self,
        callback: Callable,
        trade_pair: TradePair | None = None,
        param: dict | None = None,
    ) -> None:
        """
        - Get the fair price and will keep updating if there is any changes
        """
        topic = "fair.price"
        self.ws.subscribe(
            topic=topic,
            callback=callback,
            param = self._generate_param(
                trade_pair=trade_pair,
                param=param,
            ),
        )

    """
    ####################################################################################
    - Private Endpoint
        - Order
        - Asset
        - Position
        - Risk Limitation
        - Adl automatic reduction of position level
        - Position Mode
    ####################################################################################
    """

    def order(
        self,
        callback: Callable,
        trade_pair: TradePair | None = None,
        param: dict | None = None,
    ) -> None:
        """
        - It fetches the order list of the user's account.
        - currently on the maintanence
            - tmeporarily closed
            # TODO: keep checking the upload log of MEXC API and testing
        """
        topic = "personal.order"
        self.ws.subscribe(
            topic=topic,
            callback=callback,
            param=self._generate_param(
                trade_pair=trade_pair,
                param=param,
            ),
        )

    def asset(
        self,
        callback: Callable,
        param: dict | None = None,
    ) -> None:
        """
        func asset:
            - A function to subscribe to the asset information of the user.

        param callback:
            - The callback function to handle the asset information.
        param param:
            - Optional[dict], optional parameters for the subscription.
            - default is empty dictionary

        return None
        """
        if param is None:
            param: dict[str, str] = {}

        topic = "personal.asset"
        self.ws.subscribe(
            topic=topic,
            callback=callback,
            param=param,
        )

    def position(
        self,
        callback: Callable,
        param: dict | None = None,
    ) -> None:
        # TODO: Need to implement the position function
        raise NotImplementedError

    def risk_limitation(
        self,
        callback: Callable,
        param: dict | None = None
    ) -> None:
        # TODO: Need to implement the risk_limitation function
        if param is None:
            param = {}
        raise NotImplementedError

    def adl(
        self,
        callback: Callable,
        param: dict | None = None
    ) -> None:
        # TODO: Need to implement the adl function
        if param is None:
            param = {}
        raise NotImplementedError

    def position_mode(
        self,
        callback: Callable,
        param: dict | None = None
    ) -> None:
        # TODO: Need to implement the position_mode function
        if param is None:
            param = {}
        raise NotImplementedError


if __name__ == "__main__":
    def print_msg(msg):
        print(msg)

    mwc = MexcWebSocketClient(default_callback=print_msg)
    mwc.start()

    mwc.ticker(callback=print_msg)

    while True:
        pass
