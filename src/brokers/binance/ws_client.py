import time
from collections.abc import Callable
from typing import Literal

from src.brokers.base.ws_client import WebSocketClient
from src.brokers.base.ws_service import WebSocket
# WebSocket
from src.brokers.binance.ws_gateway import (BinanceMarketWebSocket,
                                            BinanceUserWebSocket)
# Custom Models
from src.core.models.service_dto import Ticker
from src.core.models.trade import TradePair
# Logger
from src.infrastructure.logging.set_logger import get_adapter, get_logger

logger = get_logger(__name__)


class BinanceWebSocketClient(WebSocketClient):
    @classmethod
    def _parse_trade_pair(
        cls,
        trade_pair: TradePair,
        capitalize: bool = False,
    ) -> str | None:
        if isinstance(trade_pair, TradePair):
            ticker: str = (
                trade_pair.ticker.upper() if capitalize else trade_pair.ticker.lower()
            )
            quote: str = (
                trade_pair.quote.upper() if capitalize else trade_pair.quote.lower()
            )
            return f"{ticker}{quote}"
        return "BTCUSDT" if capitalize else "btcusdt"

    def generate_timestamp(self) -> int:
        return int(time.time() * 1_000)

    def __init__(
        self,
        api_key: str | None = None,
        secret_key: str | None = None,
        name: str = "BINANCE_WEBSOCKET_CLIENT",
        ping_interval: int = 20,
        default_callback: Callable | None = None,
    ) -> None:
        """
        ;Handle one subscription at a time at the future level
        ;Composition

        ;MarketWebSocketClient
            - public endpoint
        ;UserWebSocketClient
            - private endpoint
        ;TradeWebSocketClient
            - private endpoint
        """
        super().__init__(name=name if name else "BINANCE_FUTURE_WEBSOCKET_CLIENT")
        self.logger = get_adapter(logger, f"{self.__class__.__name__}_{self.name}")

        # access point of each WebSCoektClient
        self.wss: dict[str, WebSocket] = {}

        # UserWebSocketClient - Connect to the private endpoint.
        self.wss["user"] = BinanceUserWebSocket(
            api_key=api_key,
            secret_key=secret_key,
            name=f"{self.name}_USER_WEBSOCKET",
            ping_interval=ping_interval,
        )

        # MarketWebSocketClient - Connect to the public endpoint.
        self.wss["market"] = BinanceMarketWebSocket(
            name=f"{self.name}_MARKET_WEBSOCKET",
            ping_interval=ping_interval,
        )

        # TradeWebSCoektClient - Connect to the private endpoint
        # self.wss["trade"]

    def _construct_trade_pair(self, symbol: str) -> TradePair:
        symbol_ticker: str = symbol[: len(symbol) - 4] if symbol else "BTC"
        symbol_quote: str = symbol[3:] if symbol else "USDT"
        return TradePair(ticker=symbol_ticker, quote=symbol_quote)

    def start(self):
        for key in self.wss:
            ws = self.wss[key]
            try:
                ws.start()
                self.logger.info(f"[WS_OPEN] Binance | URL: {ws.url} | Status: opened")
            except Exception as e:
                self.logger.critical(
                    f"[WS_OPEN] Binance | Error: {type(e).__name__}: {e!s}"
                )

        self._authenticate()

    """
    ####################################################################################
    User Stream
    ####################################################################################
    """

    def account_position(
        self,
        callback: Callable,
        trade_pair: TradePair | None = None,
        topic: str = "account.position",
    ) -> None:
        self._user_subscribe(callback, topic, trade_pair)

    """
    ####################################################################################
    Market Stream
    ####################################################################################
    """

    def agg_trade(
        self,
        callback: Callable,
        trade_pair: TradePair | None = None,
        req_topic: str = "aggTrade",
        push_topic: str = "aggTrade",
    ) -> None:
        """
        ;func aggTrade
            - Aggregate Trade Streams

        - Request Topic: aggTrade
        - Push Topic: aggTrade
        - Stream e.g.: btcusdt@aggTrade
        """
        stream: str = f"@{req_topic}"
        self._market_subscribe(stream, push_topic, callback, trade_pair)

    def mark_price(
        self,
    ) -> None:
        raise NotImplementedError

    def mini_ticker(
        self,
    ) -> None:
        raise NotImplementedError

    def kline(
        self,
        callback: Callable,
        trade_pair: TradePair | None = None,
        req_topic: str = "continuousKline",
        contract_type: Literal["perpetual"]
        | Literal["current_quarter"]
        | Literal["next_quarter"]
        | Literal["tradifi_perpetual"] = "perpetual",
        interval: Literal["1s"]
        | Literal["1m"]
        | Literal["3m"]
        | Literal["5m"]
        | Literal["15m"]
        | Literal["30m"]
        | Literal["1h"]
        | Literal["2h"]
        | Literal["4h"]
        | Literal["6h"]
        | Literal["8h"]
        | Literal["12h"]
        | Literal["1d"]
        | Literal["3d"]
        | Literal["1w"]
        | Literal["1M"] = "1s",
        push_topic: str = "continuous_kline",
    ) -> None:
        """
        ;func kline
            - Continuous Contract Kline Candlestick

        - Request Topic: continuousKline
        - Push Topic: continuous_kline
        - Stream Format: <symbol>_<contract_type>@continuousKline_<interval>
        - Stream e.g.: btcusdt_perpetual@continuousKline_1s
        """
        stream: str = f"_{contract_type}@{req_topic}_{interval}"
        self._market_subscribe(stream, push_topic, callback, trade_pair)

    def ticker(
        self,
        callback: Callable,
        trade_pair: TradePair | None = None,
        req_topic: str = "ticker",
        push_topic: str = "24hrTicker",
    ) -> None:
        """
        ;func ticker
        - <symbol>@ticker
        - Individual symbol ticker stream
        - topic: ticker
        - push_topic: 24hrTicker
        """

        def ticker_wrapper(msg: dict) -> None:
            symbol: str = msg.get("s")
            trade_pair: TradePair = self._construct_trade_pair(symbol)
            ticker = Ticker(
                ticker=trade_pair,
                source="Binance",
                price=float(msg.get("c", 0)),
                timestamp=int(msg.get("E", self.generate_timestamp())),
            )
            callback(ticker)

        stream: str = f"@{req_topic}"
        self._market_subscribe(stream, push_topic, ticker_wrapper, trade_pair)

    def order_book(
        self,
        callback: Callable,
        trade_pair: TradePair | None = None,
        req_topic: str = "bookTicker",
        push_topic: str = "bookTicker",
    ) -> None:
        """
        ;func order_book()
        - <symbol>@bookTicker
        """
        stream: str = f"@{req_topic}"
        self._market_subscribe(stream, push_topic, callback, trade_pair)

    def partial_book_depth(self) -> None:
        raise NotImplementedError

    def diff_book_depth(self) -> None:
        raise NotImplementedError

    def rpi_diff_book_depth(self) -> None:
        raise NotImplementedError

    def _authenticate(self) -> None:
        for ws in self.wss:
            if hasattr(ws, "authenticate"):
                ws.authenticate()

    def _market_subscribe(
        self,
        stream: str,
        push_topic: str,
        callback: Callable,
        trade_pair: TradePair | None = None,
    ) -> None:
        """
        Helper method to handle market data subscriptions and reduce code duplication.
        """
        ws = self.wss.get("market")
        stream = f"{self._parse_trade_pair(trade_pair)}{stream}"

        if not isinstance(ws, BinanceMarketWebSocket):
            self.logger.error("MarketWebSocketClient is not initialized.")
            return

        if not callable(callback):
            self.logger.error(f"The provided callback for {stream} is not callable.")
            return

        try:
            ws.subscribe(streams=stream, push_topic=push_topic, callback=callback)
            self.logger.info(
                f"[WS_SUBSCRIBE] Binance | Topic: {stream} | Status: subscribed"
            )
        except Exception as e:
            self.logger.critical(
                f"[WS_SUBSCRIBE] Binance | Error: {type(e).__name__}: {e!s}"
            )
        return

    def _user_subscribe(
        self,
        callback: Callable,
        stream: str,
        trade_pair: TradePair | None = None,
    ) -> None:
        ws = self.wss.get("user")
        symbol = self._parse_trade_pair(trade_pair, capitalize=True)

        if not isinstance(ws, BinanceUserWebSocket):
            self.logger.error(
                "[WS_SUBSCRIBE] Binance | Error: UserWebSocketClient is not initialized."
            )
            return

        if not callable(callback):
            self.logger.error(
                f"[WS_SUBSCRIBE] Binance | Error: The provided callback for {stream} is not callable."
            )
            return

        try:
            ws.subscribe(
                callback_function=callback,
                method=stream,
                params={
                    "symbol": symbol,
                },
            )
            self.logger.info(
                f"[WS_SUBSCRIBE] Binance | Topic: {stream} | Status: subscribed"
            )
        except Exception as e:
            self.logger.critical(
                f"[WS_SUBSCRIBE] Binance | Error: {type(e).__name__}: {e!s}"
            )
        return


if __name__ == "__main__":

    def print_msg(msg) -> None:
        print(msg)

    print("Binance WebSocket Client")
    bwc = BinanceWebSocketClient(
        api_key="test_api",
        secret_key="test_secret",
        default_callback=print_msg,
        name="TEST_BINANCE_WEBSOCKET_CLIENT",
    )
