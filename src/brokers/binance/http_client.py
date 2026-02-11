# Standard Library
from typing import Literal, Union

# logger
from src.infrastructure.logging.set_logger import get_logger, get_adapter

# Custom Library
from src.core.models.trade import OrderType, TimeInForce, TradePair

# RESTful Client
from src.brokers.base.http_client import HttpClient
from src.brokers.base.http_service import HttpService
from src.brokers.binance.http_gateway import BinanceFutureGateway

# Data Structure
from src.core.models.service_dto import (
    Ping,
    Ticker,
    Position
)

logger = get_logger(__name__)


class BinanceFutureHttpClient(HttpClient):
    @classmethod
    def _parse_trade_pair(
        cls,
        trade_pair: TradePair | None = None,
        capitalize: bool = True,
    ) -> str:
        if isinstance(trade_pair, TradePair):
            ticker: str = trade_pair.ticker.upper() if capitalize else trade_pair.ticker.lower()
            quote: str = trade_pair.quote.upper() if capitalize else trade_pair.quote.lower()
            return f"{ticker}{quote}"
        return "BTCUSDT" if capitalize else "btcusdt"

    @classmethod
    def _construct_trade_pair(
        cls,
        symbol: str | None = None,
    ) -> TradePair | None:
        if symbol is None:
            return TradePair("BTC", "USDT")

        # Common quote currencies in Binance futures
        quote_currencies = ["USDT"]
        
        for quote in quote_currencies:
            if symbol.endswith(quote):
                ticker = symbol[:-len(quote)]
                return TradePair(ticker, quote)
        
        # Fallback: if no common quote found, return None
        return None

    def __init__(
        self,
        api_key: str,
        secret_key: str,
        name: str | None = None,
    ) -> None:
        if name is None:
            name = "BINANCE_FUTURE_CLIENT"
        
        super().__init__(
            name=name.upper(),
        )
        self.logger = get_adapter(logger, f"{self.__class__.__name__}_{self.name}")
        
        self.gateway: HttpService = BinanceFutureGateway(
            name=f"{name.upper()}_GATEWAY",
            api_key=api_key,
            secret_key=secret_key,
        )

        self.logger.info(f"{self.name} has been initialized.")

        return

    """
    REST API Version 1 for Binance Futures.

    Market data endpoints for Binance Futures API.
    Every crypto currency trading pair is supported, while the default is "BTCUSDT".

    probably need to change this to "BTCUSDC" in the future.
    """
    # PUBLIC ENDPOINT
    def ping(
        self,
    ) -> dict:
        """
        Test connectivity to the Rest API.

        GET /fapi/v1/ping

        return: The response from the server as a dictionary.
        """
        def construct_ping_dto(msg: dict) -> Ping | None:
            ''' if dict msg is empty then it is successful, otherwise reutrn None'''
            return Ping(
                timestamp=self.generate_timestamp(),
                success=msg == {},
                source="BINANCE",
            )

        url: str = "/fapi/v1/ping"

        return construct_ping_dto(
            self.gateway.call(
                method="GET",
                url=url,
            )  # => {}
        )

    def get_server_time(
        self,
    ) -> dict:
        """
        Test connectivity to the Rest API and get the current server time.

        GET /fapi/v1/time

        return: The response from the server as a dictionary.
        """
        url: str = "/fapi/v1/time"

        return self.gateway.call(
            method="GET",
            url=url,
        )

    def get_exchange_info(
        self,
    ) -> dict:
        """
        Current exchange trading rules and symbol information.

        GET /fapi/v1/exchangeInfo

        return: The response from the server as a dictionary.
        """
        url: str = "/fapi/v1/exchangeInfo"

        return self.gateway.call(
            method="GET",
            url=url,
        )

    def get_order_book(
        self,
        symbol: TradePair | None = None,
        limit: int = 1_000,
    ) -> dict:
        """
        Get the order book for a specific symbol.

        GET /fapi/v1/depth

        param symbol: The trading pair symbol (e.g., "BTCUSDT").
        param limit: The number of order book entries to return. Default is 100; max is 5000.

        return: The response from the server as a dictionary.
        """
        url: str = "/fapi/v1/depth"
        params: dict[str, str | int] = {
            "symbol": self._parse_trade_pair(symbol),
            "limit": limit,
        }

        return self.gateway.call(
            method="GET",
            url=url,
            params=params,
        )

    def get_recent_trades(
        self,
        symbol: TradePair | None = None,
        limit: int = 1_000,
    ) -> dict:
        """
        Get recent trades for a specific symbol.

        GET /fapi/v1/trades

        param symbol: The trading pair symbol (e.g., "BTCUSDT").
        param limit: The number of trades to return. Default is 500; max is 1000.

        return: The response from the server as a dictionary.
        """
        url: str = "/fapi/v1/trades"
        params: dict[str, str | int] = {
            "symbol": self._parse_trade_pair(symbol),
            "limit": limit,
        }

        return self.gateway.call(
            method="GET",
            url=url,
            params=params,
        )

    def get_historical_trades(
        self,
        symbol: TradePair | None = None,
        limit: int = 500,
        from_id: int | None = None,
    ) -> dict:
        """
        Get historical trades for a specific symbol.

        GET /fapi/v1/historicalTrades

        param symbol: The trading pair symbol (e.g., "BTCUSDT").
        param limit: The number of trades to return. Default is 500; max is 1000.
        param from_id: Trade id to fetch from. Default gets most recent trades.

        return: The response from the server as a dictionary.
        """
        url: str = "/fapi/v1/historicalTrades"
        params: dict[str, str | int] = {
            "symbol": self._parse_trade_pair(symbol),
            "limit": limit,
        }
        if from_id is not None:
            params["fromId"] = from_id

        headers: dict[str, str] = {}
        # TODO: if api_key is None, raise an error.
        if self.gateway.api_key:
            headers["X-MBX-APIKEY"] = self.gateway.api_key

        return self.gateway.call(
            method="GET",
            url=url,
            params=params,
            headers=headers,
        )

    def get_compressed_aggregate_trades(
        self,
        symbol: TradePair | None = None,
        from_id: int | None = None,
        start_time: int | None = None,
        end_time: int | None = None,
        limit: int = 1_000,
    ) -> dict:
        """
        Get compressed, aggregate trades. Trades that fill at the same time, from the same order, with the same price will have the quantity aggregated.

        GET /fapi/v1/aggTrades

        param symbol: The trading pair symbol (e.g., "BTCUSDT").
        param from_id: ID to get aggregate trades from INCLUSIVE.
        param start_time: Timestamp in ms to get aggregate trades from INCLUSIVE.
        param end_time: Timestamp in ms to get aggregate trades until INCLUSIVE.
        param limit: The number of trades to return. Default is 500; max is 1000.

        return: The response from the server as a dictionary.
        """
        url: str = "/fapi/v1/aggTrades"
        params: dict[str, str | int] = {
            "symbol": self._parse_trade_pair(symbol),
            "limit": limit,
        }
        if from_id is not None:
            params["fromId"] = from_id
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time

        return self.gateway.call(
            method="GET",
            url=url,
            params=params,
        )

    def get_kline(
        self,
        symbol: TradePair | None = None,
        interval: str = "1m",
        startTime: int | None = None,
        endTime: int | None = None,
        limit: int | None = 500,  # maximum 1_500
    ) -> dict:
        """
        Get Kline/candlestick bars for a symbol. Klines are uniquely identified by their open time.

        GET /fapi/v1/klines

        param symbol: The trading pair symbol (e.g., "BTCUSDT").
        param interval: The interval for the klines (e.g., "1m", "5m", "1h", "1d").

        return: The response from the server as a dictionary.
        """
        url: str = "/fapi/v1/klines"
        params: dict[str, str | int] = {
            "symbol": self._parse_trade_pair(symbol),
            "interval": interval,
        }

        if startTime is not None:
            params["startTime"] = startTime
        if endTime is not None:
            params["endTime"] = endTime
        if limit is not None:
            params["limit"] = limit

        return self.gateway.call(
            method="GET",
            url=url,
            params=params,
        )

    def get_continuous_klines(
        self,
        pair: TradePair | None = None,
        contract_type: str = "PERPETUAL",
        interval: str = "1m",
        startTime: int | None = None,
        endTime: int | None = None,
        limit: int | None = 500,  # maximum 1_500
    ) -> dict:
        """
        Get Kline/candlestick bars for a specific pair and contract type. Klines are uniquely identified by their open time.

        GET /fapi/v1/continuousKlines

        param pair: The trading pair (e.g., "BTCUSDT").
        param contract_type: The contract type (e.g., "PERPETUAL", "CURRENT_MONTH", "NEXT_MONTH", "CURRENT_QUARTER", "NEXT_QUARTER").
        param interval: The interval for the klines (e.g., "1m", "5m", "1h", "1d").

        return: The response from the server as a dictionary.
        """
        url: str = "/fapi/v1/continuousKlines"
        params: dict[str, str | int] = {
            "pair": self._parse_trade_pair(pair),
            "contractType": contract_type,
            "interval": interval,
        }

        if startTime is not None:
            params["startTime"] = startTime
        if endTime is not None:
            params["endTime"] = endTime
        if limit is not None:
            params["limit"] = limit

        return self.gateway.call(
            method="GET",
            url=url,
            params=params,
        )

    def get_index_price_klines(
        self,
        pair: TradePair | None = None,
        interval: str = "1m",
        startTime: int | None = None,
        endTime: int | None = None,
        limit: int | None = 500,  # maximum 1_500
    ) -> dict:
        """
        Get Kline/candlestick bars for a specific symbol's index price. Klines are uniquely identified by their open time.

        GET /fapi/v1/indexPriceKlines

        param symbol: The trading pair symbol (e.g., "BTCUSDT").
        param interval: The interval for the klines (e.g., "1m", "5m", "1h", "1d").

        return: The response from the server as a dictionary.
        """
        url: str = "/fapi/v1/indexPriceKlines"
        params: dict[str, str | int] = {
            "pair": self._parse_trade_pair(pair),
            "interval": interval,
        }

        if startTime is not None:
            params["startTime"] = startTime
        if endTime is not None:
            params["endTime"] = endTime
        if limit is not None:
            params["limit"] = limit

        return self.gateway.call(
            method="GET",
            url=url,
            params=params,
        )

    def get_mark_price_klines(
        self,
        symbol: TradePair | None = None,
        interval: str = "1m",
        startTime: int | None = None,
        endTime: int | None = None,
        limit: int | None = 500,  # maximum 1_500
    ) -> dict:
        """
        Get Kline/candlestick bars for a specific symbol's mark price. Klines are uniquely identified by their open time.

        GET /fapi/v1/markPriceKlines

        param symbol: The trading pair symbol (e.g., "BTCUSDT").
        param interval: The interval for the klines (e.g., "1m", "5m", "1h", "1d").

        return: The response from the server as a dictionary.
        """
        url: str = "/fapi/v1/markPriceKlines"
        params: dict[str, str | int] = {
            "symbol": self._parse_trade_pair(symbol),
            "interval": interval,
        }

        if startTime is not None:
            params["startTime"] = startTime
        if endTime is not None:
            params["endTime"] = endTime
        if limit is not None:
            params["limit"] = limit

        return self.gateway.call(
            method="GET",
            url=url,
            params=params,
        )

    def get_premium_klines(
        self,
        symbol: TradePair | None = None,
        interval: str = "1m",
        startTime: int | None = None,
        endTime: int | None = None,
        limit: int | None = 500,  # maximum 1_500
    ) -> dict:
        """
        Get Kline/candlestick bars for a specific symbol's premium index. Klines are uniquely identified by their open time.

        GET /fapi/v1/premiumIndexKlines

        param symbol: The trading pair symbol (e.g., "BTCUSDT").
        param interval: The interval for the klines (e.g., "1m", "5m", "1h", "1d").

        return: The response from the server as a dictionary.
        """
        url: str = "/fapi/v1/premiumIndexKlines"
        params: dict[str, str | int] = {
            "symbol": self._parse_trade_pair(symbol),
            "interval": interval,
        }

        if startTime is not None:
            params["startTime"] = startTime
        if endTime is not None:
            params["endTime"] = endTime
        if limit is not None:
            params["limit"] = limit

        return self.gateway.call(
            method="GET",
            url=url,
            params=params,
        )

    def get_mark_price(
        self,
        symbol: TradePair | None = None,
    ) -> dict:
        """
        Get the current mark price and funding rate for a specific symbol.

        GET /fapi/v1/premiumIndex

        param symbol: The trading pair symbol (e.g., "BTCUSDT").

        return: The response from the server as a dictionary.
        """
        url: str = "/fapi/v1/premiumIndex"
        params: dict[str, str] = {
            "symbol": self._parse_trade_pair(symbol),
        }

        return self.gateway.call(
            method="GET",
            url=url,
            params=params,
        )

    def get_funding_rate_history(
        self,
        symbol: TradePair | None = None,
        startTime: int | None = None,
        endTime: int | None = None,
        limit: int = 100,  # maximum 1_000
    ) -> dict:
        """
        Get the funding rate history for a specific symbol.

        GET /fapi/v1/fundingRate

        param symbol: The trading pair symbol (e.g., "BTCUSDT").
        param startTime: Timestamp in ms to get funding rate history from INCLUSIVE.
        param endTime: Timestamp in ms to get funding rate history until INCLUSIVE.
        param limit: The number of records to return. Default is 100; max is 1000.

        return: The response from the server as a dictionary.
        """
        url: str = "/fapi/v1/fundingRate"
        params: dict[str, str | int] = {
            "symbol": self._parse_trade_pair(symbol),
            "limit": limit,
        }
        if startTime is not None:
            params["startTime"] = startTime
        if endTime is not None:
            params["endTime"] = endTime

        return self.gateway.call(
            method="GET",
            url=url,
            params=params,
        )

    def get_funding_rate_info(
        self,
    ) -> dict:
        """
        Get the current funding rate and funding rate history for all symbols.

        GET /fapi/v1/fundingRate

        return: The response from the server as a dictionary.
        """
        url: str = "/fapi/v1/fundingRate"

        return self.gateway.call(
            method="GET",
            url=url,
        )

    def get_ticker(
        self,
        symbol: TradePair | None = None,
    ) -> Ticker | None:
        """
        Get 24 hour rolling window price change statistics for a specific symbol.

        GET /fapi/v1/ticker/24hr

        param symbol: The trading pair symbol (e.g., "BTCUSDT").

        return: The response from the server as a dictionary.
        """
        symbol = symbol if symbol else TradePair('BTC', 'USDT')

        def construct_ticker_dto(data: dict) -> Ticker | None:
            if isinstance(data, dict):
                return Ticker(
                    timestamp=self.generate_timestamp(),
                    source="BINANCE",
                    ticker=symbol,
                    price=data.get('lastPrice', 0.0),
                )
            else:
                return

        url: str = "/fapi/v1/ticker/24hr"
        params: dict[str, str] = {
            "symbol": self._parse_trade_pair(symbol),
        }

        return construct_ticker_dto(
            self.gateway.call(
                method="GET",
                url=url,
                params=params,
            )
        )

    def get_top_trader_long_short_ratio(
        self,
        symbol: TradePair | None = None,
        period: str = "5m",
        limit: int = 30,  # maximum 500,
        startTime: int | None = None,
        endTime: int | None = None,
    ) -> dict:
        """
        - Get the long/short ratio of top traders for a specific symbol and time period.
        """
        url: str = "/futures/data/topLongShortAccountRatio"
        params: dict[str, str | int] = {
            "symbol": self._parse_trade_pair(symbol),
            "period": period,
            "limit": limit,
        }
        if startTime is not None:
            params["startTime"] = startTime
        if endTime is not None:
            params["endTime"] = endTime

        return self.gateway.call(
            method="GET",
            url=url,
            params=params,
        )

    def get_long_short_ratio(
        self,
        symbol: TradePair | None = None,
        period: str = "5m",
        limit: int = 30,  # maximum 500,
        startTime: int | None = None,
        endTime: int | None = None,
    ) -> dict:
        """
        - Get the long/short ratio for a specific symbol and time period.
        """
        url: str = "/futures/data/globalLongShortAccountRatio"
        params: dict[str, str | int] = {
            "symbol": self._parse_trade_pair(symbol),
            "period": period,
            "limit": limit,
        }
        if startTime is not None:
            params["startTime"] = startTime
        if endTime is not None:
            params["endTime"] = endTime

        return self.gateway.call(
            method="GET",
            url=url,
            params=params,
        )

    def get_taker_buy_sell_volume(
        self,
        symbol: TradePair | None = None,
        period: str = "5m",  # 5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d
        limit: int = 30,  # maximum 500,
        start_time: int | None = None,
        end_time: int | None = None,
    ) -> dict:
        """
        - Get the taker buy/sell volume for a specific symbol and time period.
        """
        url: str = "/futures/data/takerlongshortRatio"
        params: dict[str, str | int] = {
            "symbol": self._parse_trade_pair(symbol),
            "period": period,
            "limit": limit,
        }
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time

        return self.gateway.call(
            method="GET",
            url=url,
            params=params,
        )

    def get_basis(
        self,
        pair: TradePair | None = None,
        contract_type: str = "PERPETUAL",
        period: str = "5m",  # 5m, 15m, 30m, 1h, 2h, 4h, 6h, 12h, 1d
        limit: int = 30,  # maximum 500,
        startTime: int | None = None,
        endTime: int | None = None,
    ) -> dict:
        """
        - Get the basis for a specific pair, contract type, and time period.
        """
        url: str = "/futures/data/basis"
        params: dict[str, str | int] = {
            "pair": self._parse_trade_pair(pair),
            "contractType": contract_type,
            "period": period,
            "limit": limit,
        }
        if startTime is not None:
            params["startTime"] = startTime
        if endTime is not None:
            params["endTime"] = endTime

        return self.gateway.call(
            method="GET",
            url=url,
            params=params,
        )

    def get_composite_index_symbol_info(
        self,
        symbol: TradePair | None = None,
    ) -> dict:
        """
        - Get the composite index symbol information.
        """
        url: str = "/fapi/v1/indexInfo"
        params: dict[str, str] = {
            "symbol": self._parse_trade_pair(symbol),
        }

        return self.gateway.call(
            method="GET",
            url=url,
            params=params,
        )

    def get_asset_index(
        self,
        symbol: TradePair | None = None,
    ) -> dict:
        """
        - asset index for multi-assets mode.
        """
        url: str = "/fapi/v1/assetIndex"
        params: dict[str, str] = {
            "symbol": self._parse_trade_pair(symbol),
            # "timestamp": FutureMarket.generate_timestmap(),
        }

        return self.gateway.call(
            method="GET",
            url=url,
            params=params,
        )

    def get_index_price_constituents(
        self,
        symbol: TradePair | None = None,
    ) -> dict:
        """
        - Query index price constituents.
        """
        url: str = "/fapi/v1/indexPriceConstituents"
        params: dict[str, str] = {
            "symbol": self._parse_trade_pair(symbol),
        }

        return self.gateway.call(
            method="GET",
            url=url,
            params=params,
        )

    """
    # ORDER ENDPOINTS
    # For Post, need to keep the order of items in the params.
    # we are not using the

    # SL
    {
        "symbol": "BTCUSDT",
        "side": "<OPPOSITE_OF_ORIGINAL_ORDER>",
        "type": "STOP_MARKET",
        "stopPrice": "<SL_PRICE>",
        "workingType": "MARK_PRICE",
        "closePosition": "true",
        "timestamp": "<ms>",
        "recvWindow": 5000
    }

    # TP
    {
        "symbol": "BTCUSDT",
        "side": "<OPPOSITE_OF_ORIGINAL_ORDER>",
        "type": "TAKE_PROFIT_MARKET",
        "stopPrice": "<TP_PRICE>",
        "workingType": "MARK_PRICE",
        "closePosition": "true",
        "timestamp": "<ms>",
        "recvWindow": 5000
    }
    """
    def order(
        self,
        sl_price: float,
        tp_price: float,
        leverage: int,
        symbol_curr_quantity: float,  # get it from the binance websocket possibly.
        symbol: TradePair | None = None,
        side: Literal["BUY", "SELL"] = "BUY",
        recv_window: int = 5_000,
    ) -> None:
        '''
        - Call three different place_order():
            - one for the original position
            - Others for TP and SL

        - calculating the btc quantity:
            - NUM_OF_BTC = floor((USDT_AMT) / (markPrice) to stepSize)
        '''
        # ORDER

        # TODO: decide the following:
        # Sequential manner or multi-threaded manner?
        self.change_initial_leverage(
            leverage=leverage,
        )  # change the leverage to the default, 5 for now.

        # MAIN ORDER
        res = self.place_order(
            symbol=symbol,
            side=side,
            type="MARKET",
            quantity=symbol_curr_quantity,
            recv_window=recv_window,
        )
        if (res.get("status") == "NEW"):
            self.logger.info("The new order has been opened.")

        # STOP LOSS
        self.place_order(
            symbol=symbol,
            stop_price=sl_price,
            type="STOP_MARKET",
            side="BUY" if side == "SELL" else "SELL",  # Opposite of the Main Order
            close_position="true",
            time_in_force="GTE_GTC",
        )
        self.logger.info(f"The new order's STOP LOSS PRICE is at {sl_price}.")

        # TAKE PROFIT
        self.place_order(
            symbol=symbol,
            stop_price=tp_price,
            type="TAKE_PROFIT_MARKET",
            side="BUY" if side == "SELL" else "SELL",  # Opposite of the Main Order
            close_position="true",
            time_in_force="GTE_GTC",
        )
        self.logger.info(f"The new order's TAKE PROFIT PRICE is at {tp_price}.")

        return

    def place_order(
        self,
        side: Union[Literal["BUY"], Literal["SELL"]],
        symbol: TradePair | None = None,
        position_side: str | None = None,  # "BOTH", "LONG", "SHORT", None
        type: Union[Literal["MARKET"], Literal["TAKE_PROFIT_MARKET"], Literal["STOP_MARKET"]] = "MARKET",
        quantity: float | None = None,
        reduce_only: str | None = None,
        time_in_force: str | None = None,
        price: float | None = None,
        new_client_order_id: str | None = None,
        stop_price: float | None = None,
        close_position: Union[Literal["true"], Literal["false"]] | None = None,  # bool: true or false
        activation_price: float | None = None,
        callback_rate: float | None = None,
        working_type: str | None = None,
        price_protect: str | None = None,
        new_order_resp_type: str | None = None,
        price_match: str | None = None,
        self_trade_prevention_mode: str | None = None,
        good_till_date: int | None = None,
        recv_window: int | None = 5_000,  # 5_000 ms is the default value, i.e., 5 sec.
        url: str = "/fapi/v1/order",
    ) -> dict | None:
        '''
        - new_order()
            - make a new order in the Binance FUTURE Market

        - basic requirements:
            - the order should be in market order.
            - to provide the SL price and TP price.
            - to provide the USDT Amount to buy or sell. (NOT BTC AMT)
            - to set the leverage, 20 by default.

        '''
        params: dict[str, int | float | str] = dict(
            symbol=self._parse_trade_pair(symbol),
            side=side,
            position_side=position_side,
            type=type,
            time_in_force=time_in_force,
            quantity=quantity,
            reduce_only=reduce_only,
            price=price,
            new_client_order_id=new_client_order_id,
            stop_price=stop_price,
            close_position=close_position,
            activation_price=activation_price,
            callback_rate=callback_rate,
            working_type=working_type,
            price_protect=price_protect,
            new_order_resp_type=new_order_resp_type,
            price_match=price_match,
            self_trade_prevention_mode=self_trade_prevention_mode,
            good_till_date=good_till_date,
            recv_window=recv_window,
            timestamp=self.generate_timestamp(),
        )

        return self.gateway.call(
            method="POST",
            params=params,
            url=url,
        )

    def place_multiple_orders(
        self,
    ):
        raise NotImplementedError
        return

    def change_order(
        self,
    ):
        raise NotImplementedError
        return

    def change_multiple_orders(
        self,
    ):
        raise NotImplementedError
        return

    def get_order_change_history(
        self,
    ):
        raise NotImplementedError
        return

    def cancel_order(
        self,
    ):
        raise NotImplementedError
        return

    def cancel_multiple_orders(self,):
        raise NotImplementedError
        return

    def cancel_all_orders(
        self,
    ):
        raise NotImplementedError
        return

    def auto_cancel_all_open_orders(
        self,
    ):
        raise NotImplementedError
        return

    def query_order(self,):
        raise NotImplementedError
        return

    def get_all_orders(
        self,
        symbol: TradePair | None = None,
        order_id: int | None = None,
        start_time: int | None = None,
        end_time: int | None = None,
        limit: int | None = 500,  # max 1_000
        recv_window: int | None = 5_000,
        timestamp: int | None = None,
    ) -> list[dict] | None:
        """
        Get all orders for a specific symbol.

        GET /fapi/v1/allOrders

        param symbol: The trading pair symbol.
        param order_id: Filter by a specific order ID.
        param start_time: Timestamp in ms to get orders from INCLUSIVE.
        param end_time: Timestamp in ms to get orders until INCLUSIVE.
        param limit: The number of orders to return. Default is 500; max is 1000.
        param recv_window: The request weight limit in milliseconds.
        param timestamp: Custom timestamp override.

        return: List of orders as dictionaries.
        """
        url: str = "/fapi/v1/allOrders"
        params: dict[str, int | str] = {
            "symbol": self._parse_trade_pair(symbol),
            "timestamp": timestamp if timestamp is not None else self.generate_timestamp(),
        }

        # Add optional parameters if provided
        optional_params = {
            "orderId": order_id,
            "startTime": start_time,
            "endTime": end_time,
            "limit": limit,
            "recvWindow": recv_window,
        }
        for key, value in optional_params.items():
            if value is not None:
                params[key] = value

        return self.gateway.call(
            method="GET",
            url=url,
            params=params,
        )

    def get_open_order(self,):
        raise NotImplementedError
        return

    def get_open_orders(
        self,
        url: str = "/fapi/v1/openOrders",
        symbol: TradePair | None = None,
        recv_window: int = 5_000,
    ) -> list[Position] | None:
        """
        Get all open orders for a specific symbol.

        GET /fapi/v1/openOrders

        param symbol: The trading pair symbol.
        param recv_window: The request weight limit in milliseconds.

        return: List of open Position objects.
        """
        def generate_position_dto(orders: list[dict]) -> list[Position]:
            positions: list[Position] = []
            for order in orders:
                orig_qty = float(order.get("origQty", 0))

                # Omit orders with 0 quantity (dummy data)
                if orig_qty == 0:
                    continue

                position = Position(
                    timestamp=self.generate_timestamp(),
                    source="BINANCE",
                    id=order.get("orderId", 0),
                    ticker=self._construct_trade_pair(order.get("symbol")),
                    status=order.get("status", ""),
                    time_in_force=TimeInForce[order.get("timeInForce", "GTC")],
                    order_type=OrderType[order.get("type", "MARKET")],
                    side=order.get("side", ""),
                    position_side=order.get("positionSide", "BOTH"),
                    orig_qty=orig_qty,
                    executed_qty=float(order.get("executedQty", 0)),
                    avg_price=float(order.get("avgPrice", 0)),
                    cum_quote=float(order.get("cumQuote", 0)),
                    price=float(order.get("price", 0)),
                    stop_price=float(order.get("stopPrice", 0)),
                    reduce_only=order.get("reduceOnly", False),
                    close_position=order.get("closePosition", False),
                    order_time=order.get("time", 0),
                    update_time=order.get("updateTime", 0),
                    client_order_id=order.get("clientOrderId", ""),
                    working_type=order.get("workingType", "CONTRACT_PRICE"),
                    price_match=order.get("priceMatch", "NONE"),
                    self_trade_prevention_mode=order.get("selfTradePreventionMode", "NONE"),
                    good_till_date=order.get("goodTillDate", 0),
                    price_protect=order.get("priceProtect", False),
                    activate_price=float(order.get("activatePrice", 0)) if "activatePrice" in order else 0.0,
                    price_rate=float(order.get("priceRate", 0)) if "priceRate" in order else 0.0,
                )
                positions.append(position)

            return positions

        params: dict[str, int | str] = {
            "symbol": self._parse_trade_pair(symbol),
            "recv_window": recv_window,
            "timestamp": self.generate_timestamp(),
        }

        orders: list[dict] | None = self.gateway.call(
            method="GET",
            url=url,
            params=params,
        )

        if not isinstance(orders, list) or len(orders) == 0:
            return []
        
        return generate_position_dto(orders)

    def query_account_trades(self,):
        raise NotImplementedError
        return

    def query_user_force_orders(self,):
        raise NotImplementedError
        return

    def change_margin_type(self,):
        raise NotImplementedError
        return

    def change_position_mode(self,):
        raise NotImplementedError
        return

    def change_initial_leverage(
        self,
        url: str = "/fapi/v1/leverage",
        symbol: TradePair | None = None,
        leverage: int = 10,  # originally 20, but let's keep it safe. 5 or 10.
        recvWindow: int = 5000,
    ):
        params = {
            "symbol": self._parse_trade_pair(symbol),
            "leverage": leverage,
            "recvWindow": recvWindow,
            "timestamp": self.generate_timestamp(),
        }

        return self.gateway.call(
            method="POST",
            url=url,
            params=params,
        )

    def change_multi_assets_mode(self,):
        raise NotImplementedError
        return

    def change_isolated_position_margin(
        self,
    ):
        raise NotImplementedError
        return

    def postion_info_v2(self,):
        raise NotImplementedError
        return

    def position_info_v3(self,):
        raise NotImplementedError
        return

    def position_adl_quantile_estimation(self,):
        raise NotImplementedError
        return

    def get_position_margin_history(self,):
        return

    def test_new_order(self,):
        raise NotImplementedError
        return

    def get_account_balance(
        self,
        url: str = "/fapi/v3/balance",
        recv_window: int = 5_000,
        asset: str = "USDT",
    ) -> dict | None:
        params: dict[str, int] = {
            "recvWindow": recv_window,
            "timestamp": self.generate_timestamp(),
            "asset": asset,
        }

        return self.gateway.call(
            method="GET",
            params = params,
            url = url,
        )

    def get_account_information_v2(
        self,
        url: str = "/fapi/v2/account",
        recv_window: int = 5_000,
    ) -> dict | None:
        params: dict[str, int] = {
            "recvWindow": recv_window,
            "timestamp": self.generate_timestamp(),
        }

        return self.gateway.call(
            method="GET",
            params = params,
            url = url,
        )

    def get_position_information_v2(
        self,
        url: str = "/fapi/v2/positionRisk",
        symbol: TradePair | None = None,
        recv_window: int = 5_000,
    ) -> list[dict | None]:
        params: dict[str, int | float] = {
            "symbol": self._parse_trade_pair(symbol),
            "recv_window": recv_window,
            "timestamp": self.generate_timestamp(),
        }

        return self.gateway.call(
            method="GET",
            url=url,
            params=params,
        )

    def get_positions(self):
        raise NotImplementedError

    # TODO: need to re-implement the function
    def get_current_open_order(
        self,
        url: str = "/fapi/v1/openOrder",
        symbol: TradePair | None = None,
        recv_window: int = 5_000,
    ):
        params: dict[str, int | float] = {
            "symbol": self._parse_trade_pair(symbol),
            "recv_window": recv_window,
            "timestamp": self.generate_timestamp()
        }

        return self.gateway.call(
            method="GET",
            url=url,
            params=params,
        )

    def get_all_open_order(
        self,
        url: str = "/fapi/v1/openOrders",
        symbol: TradePair | None = None,
        recv_window = 5_000,
    ):
        params: dict[str, int | float] = {
            "symbol": self._parse_trade_pair(symbol),
            "recv_window": recv_window,
            "timestamp": self.generate_timestamp(),
        }

        return self.gateway.call(
            method="GET",
            url=url,
            params=params,
        )


if __name__ == "__main__":
    from dotenv import load_dotenv
    import os

    load_dotenv()

    bfc = BinanceFutureHttpClient(
        name="TEST_BINANCE_FUTURE_RESTFUL",
        api_key=os.getenv("BINANCE_HMAC_API_KEY"),
        secret_key=os.getenv("BINANCE_HMAC_SECRET_KEY"),
    )

    print(bfc.ping())
    # response = bfc.get_all_orders()
    # for res in response:
    #     print(res)
