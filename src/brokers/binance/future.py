# Standard Library
from typing import Literal, Union
from collections.abc import Callable
import time


# Custom Library
from src.core.models.websocket_dto import Ticker
from src.infrastructure.logging.set_logger import operation_logger
from src.brokers.binance.base_sdk import FutureBase
from src.brokers.binance.websocket_base import (
    BinanceMarketWebSocket,
    BinanceUserWebSocket
)
from src.brokers.base.websocket_sdk import WebSocketClient, WebSocket
from src.core.models.trade import TradePair


class FutureMarket(FutureBase):
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
        url: str = "/fapi/v1/ping"

        return self.call(
            method = "GET",
            url = url,
        )

    def server_time(
        self,
    ) -> dict:
        """
        Test connectivity to the Rest API and get the current server time.

        GET /fapi/v1/time

        return: The response from the server as a dictionary.
        """
        url: str = "/fapi/v1/time"

        return self.call(
            method = "GET",
            url = url,
        )

    def exchange_info(
        self,
    ) -> dict:
        """
        Current exchange trading rules and symbol information.

        GET /fapi/v1/exchangeInfo

        return: The response from the server as a dictionary.
        """
        url: str = "/fapi/v1/exchangeInfo"

        return self.call(
            method = "GET",
            url = url,
        )

    def order_book(
        self,
        symbol: str = "BTCUSDT",
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
            "symbol": symbol,
            "limit": limit,
        }

        return self.call(
            method = "GET",
            url = url,
            params = params,
        )

    def recent_trades(
        self,
        symbol: str = "BTCUSDT",
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
            "symbol": symbol,
            "limit": limit,
        }

        return self.call(
            method = "GET",
            url = url,
            params = params,
        )

    def historical_trades(
        self,
        symbol: str = "BTCUSDT",
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
            "symbol": symbol,
            "limit": limit,
        }
        if from_id is not None:
            params["fromId"] = from_id

        headers: dict[str, str] = {}
        # TODO: if api_key is None, raise an error.
        if self.api_key:
            headers["X-MBX-APIKEY"] = self.api_key

        return self.call(
            method = "GET",
            url = url,
            params = params,
            headers = headers,
        )

    def compressed_aggregate_trades(
        self,
        symbol: str = "BTCUSDT",
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
            "symbol": symbol,
            "limit": limit,
        }
        if from_id is not None:
            params["fromId"] = from_id
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time

        return self.call(
            method = "GET",
            url = url,
            params = params,
        )

    def klines(
        self,
        symbol: str = "BTCUSDT",
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
            "symbol": symbol,
            "interval": interval,
        }

        if startTime is not None:
            params["startTime"] = startTime
        if endTime is not None:
            params["endTime"] = endTime
        if limit is not None:
            params["limit"] = limit

        return self.call(
            method = "GET",
            url = url,
            params = params,
        )

    def continuous_klines(
        self,
        pair: str = "BTCUSDT",
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
            "pair": pair,
            "contractType": contract_type,
            "interval": interval,
        }

        if startTime is not None:
            params["startTime"] = startTime
        if endTime is not None:
            params["endTime"] = endTime
        if limit is not None:
            params["limit"] = limit

        return self.call(
            method = "GET",
            url = url,
            params = params,
        )

    def index_price_klines(
        self,
        pair: str = "BTCUSDT",
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
            "pair": pair,
            "interval": interval,
        }

        if startTime is not None:
            params["startTime"] = startTime
        if endTime is not None:
            params["endTime"] = endTime
        if limit is not None:
            params["limit"] = limit

        return self.call(
            method = "GET",
            url = url,
            params = params,
        )

    def mark_price_klines(
        self,
        symbol: str = "BTCUSDT",
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
            "symbol": symbol,
            "interval": interval,
        }

        if startTime is not None:
            params["startTime"] = startTime
        if endTime is not None:
            params["endTime"] = endTime
        if limit is not None:
            params["limit"] = limit

        return self.call(
            method = "GET",
            url = url,
            params = params,
        )

    def premium_klines(
        self,
        symbol: str = "BTCUSDT",
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
            "symbol": symbol,
            "interval": interval,
        }

        if startTime is not None:
            params["startTime"] = startTime
        if endTime is not None:
            params["endTime"] = endTime
        if limit is not None:
            params["limit"] = limit

        return self.call(
            method = "GET",
            url = url,
            params = params,
        )

    def mark_price(
        self,
        symbol: str = "BTCUSDT",
    ) -> dict:
        """
        Get the current mark price and funding rate for a specific symbol.

        GET /fapi/v1/premiumIndex

        param symbol: The trading pair symbol (e.g., "BTCUSDT").

        return: The response from the server as a dictionary.
        """
        url: str = "/fapi/v1/premiumIndex"
        params: dict[str, str] = {
            "symbol": symbol,
        }

        return self.call(
            method = "GET",
            url = url,
            params = params,
        )

    def funding_rate_history(
        self,
        symbol: str = "BTCUSDT",
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
            "symbol": symbol,
            "limit": limit,
        }
        if startTime is not None:
            params["startTime"] = startTime
        if endTime is not None:
            params["endTime"] = endTime

        return self.call(
            method = "GET",
            url = url,
            params = params,
        )

    def funding_rate_info(
        self,
    ) -> dict:
        """
        Get the current funding rate and funding rate history for all symbols.

        GET /fapi/v1/fundingRate

        return: The response from the server as a dictionary.
        """
        url: str = "/fapi/v1/fundingRate"

        return self.call(
            method = "GET",
            url = url,
        )

    def ticker_24hr(
        self,
        symbol: str = "BTCUSDT",
    ) -> dict:
        """
        Get 24 hour rolling window price change statistics for a specific symbol.

        GET /fapi/v1/ticker/24hr

        param symbol: The trading pair symbol (e.g., "BTCUSDT").

        return: The response from the server as a dictionary.
        """
        url: str = "/fapi/v1/ticker/24hr"
        params: dict[str, str] = {
            "symbol": symbol,
        }

        return self.call(
            method = "GET",
            url = url,
            params = params,
        )

    def top_trader_long_short_ratio(
        self,
        symbol: str = "BTCUSDT",
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
            "symbol": symbol,
            "period": period,
            "limit": limit,
        }
        if startTime is not None:
            params["startTime"] = startTime
        if endTime is not None:
            params["endTime"] = endTime

        return self.call(
            method = "GET",
            url = url,
            params = params,
        )

    def long_short_ratio(
        self,
        symbol: str = "BTCUSDT",
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
            "symbol": symbol,
            "period": period,
            "limit": limit,
        }
        if startTime is not None:
            params["startTime"] = startTime
        if endTime is not None:
            params["endTime"] = endTime

        return self.call(
            method = "GET",
            url = url,
            params = params,
        )

    def taker_busy_sell_volume(
        self,
        symbol: str = "BTCUSDT",
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
            "symbol": symbol,
            "period": period,
            "limit": limit,
        }
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time

        return self.call(
            method = "GET",
            url = url,
            params = params,
        )

    def basis(
        self,
        pair: str = "BTCUSDT",
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
            "pair": pair,
            "contractType": contract_type,
            "period": period,
            "limit": limit,
        }
        if startTime is not None:
            params["startTime"] = startTime
        if endTime is not None:
            params["endTime"] = endTime

        return self.call(
            method = "GET",
            url = url,
            params = params,
        )

    def composite_index_symbol_info(
        self,
        symbol: str | None = "BTCUSDT",
    ) -> dict:
        """
        - Get the composite index symbol information.
        """
        url: str = "/fapi/v1/indexInfo"
        params: dict[str, str] = {
            "symbol": symbol,
        }

        return self.call(
            method = "GET",
            url = url,
            params = params,
        )

    def asset_index(
        self,
        symbol: str = "BTCUSDT",
    ) -> dict:
        """
        - asset index for multi-assets mode.
        """
        url: str = "/fapi/v1/assetIndex"
        params: dict[str, str] = {
            "symbol": symbol,
            # "timestamp": FutureMarket.generate_timestmap(),
        }

        return self.call(
            method = "GET",
            url = url,
            params = params,
        )

    def query_index_price_consituents(
        self,
        symbol: str = "BTCUSDT",
    ) -> dict:
        """
        - Query index price constituents.
        """
        url: str = "/fapi/v1/indexPriceConstituents"
        params: dict[str, str] = {
            "symbol": symbol,
        }

        return self.call(
            method = "GET",
            url = url,
            params = params,
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
        symbol: str = "BTCUSDT",
        side: str = Union[Literal["BUY"], Literal["SELL"]],
        recv_window: int = 5_000,
    ) -> None:
        '''
        - Call three different new_order():
            - one for the original position
            - Others for TP and SL

        - calculating the btc quantity:
            - NUM_OF_BTC = floor((USDT_AMT) / (markPrice) to stepSize)
        '''
        # ORDER

        # TODO: decide the following:
        # Sequential manner or multi-threaded manner?
        self.change_initial_leverage(
            leverage = leverage,
        )  # change the leverage to the default, 5 for now.

        # MAIN ORDER
        res = self.new_order(
            symbol = symbol,
            side = side,
            type = "MARKET",
            quantity = symbol_curr_quantity,
            recv_window = recv_window,
        )
        if (res.get("status") == "NEW"):
            operation_logger.info(f"{__name__} - The new order has been opened.")

        # STOP LOSS
        self.new_order(
            symbol = symbol,
            stop_price = sl_price,
            type = "STOP_MARKET",
            side = "BUY" if side == "SELL" else "SELL",  # Opposite of the Main Order
            close_position = "true",
            time_in_force = "GTE_GTC",
        )
        operation_logger.info(f"{__name__} - The new order's STOP LOSS PRICE is at {sl_price}.")

        # TAKE PROFIT
        self.new_order(
            symbol = symbol,
            stop_price = tp_price,
            type = "TAKE_PROFIT_MARKET",
            side = "BUY" if side == "SELL" else "SELL",  # Opposite of the Main Order
            close_position = "true",
            time_in_force = "GTE_GTC",
        )
        operation_logger.info(f"{__name__} - The new order's TAKE PROFIT PRICE is at {tp_price}.")

        return

    def new_order(
        self,
        side: Union[Literal["BUY"], Literal["SELL"]],
        symbol: str = "BTCUSDT",
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
            symbol = symbol,
            side = side,
            position_side = position_side,
            type = type,
            time_in_force = time_in_force,
            quantity = quantity,
            reduce_only = reduce_only,
            price = price,
            new_client_order_id = new_client_order_id,
            stop_price = stop_price,
            close_position = close_position,
            activation_price = activation_price,
            callback_rate = callback_rate,
            working_type = working_type,
            price_protect = price_protect,
            new_order_resp_type = new_order_resp_type,
            price_match = price_match,
            self_trade_prevention_mode = self_trade_prevention_mode,
            good_till_date = good_till_date,
            recv_window = recv_window,
            timestamp = self.generate_timestamp(),
        )

        return self.call(
            method = "POST",
            params = params,
            url = url,
        )

    def multiple_orders(
        self,
    ):
        raise NotImplementedError
        return

    def modify_order(
        self,
    ):
        raise NotImplementedError
        return

    def modify_multiple_orders(
        self,
    ):
        raise NotImplementedError
        return

    def get_order_modify_history(
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

    def query_all_orders(
        self,
        symbol: str = "BTCUSDT",
        order_id: int | None = None,
        start_time: int | None = None,
        end_time: int | None = None,
        limit: int | None = 500,  # max 1_000
        recv_window: int | None = 5_000,
        timestamp: int | None = None,
    ):
        url: str = "/fapi/v1/allOrders"

        params: dict[str, int | str] = {
            "symbol": symbol,
            "timestamp": timestamp if timestamp is not None else self.generate_timestamp(),
        }

        if order_id is not None:
            params["orderId"] = order_id
        if start_time is not None:
            params["startTime"] = start_time
        if end_time is not None:
            params["endTime"] = end_time
        if limit is not None:
            params["limit"] = limit
        if recv_window is not None:
            params["recvWindow"] = recv_window

        return self.call(
            method = "GET",
            url = url,
            params = params,
        )

    def query_open_order(self,):
        raise NotImplementedError
        return

    def query_all_open_orders(
        self,
        url: str = "/fapi/v1/openOrders",
        symbol: str = "BTCUSDT",
        recv_window: int = 5_000,
    ) -> dict | None:
        params: dict[str, int] = dict(
            symbol = symbol,
            recv_window = recv_window,
            timestamp = self.generate_timestamp(),
        )

        return self.call(
            method = "GET",
            url = url,
            params = params,
        )

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
        symbol: str = "BTCUSDT",
        leverage: int = 10,  # originally 20, but let's keep it safe. 5 or 10.
        recvWindow: int = 5000,
    ):
        params = {
            "symbol": symbol,
            "leverage": leverage,
            "recvWindow": recvWindow,
            "timestamp": self.generate_timestamp(),
        }

        return self.call(
            method = "POST",
            url = url,
            params = params,
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

    def future_account_balance_v3(
        self,
        url: str = "/fapi/v3/balance",
        recv_window: int = 5_000,
        asset: str = "USDT",
    ) -> dict | None:
        params: dict[str, int] = dict(
            recvWindow = recv_window,
            timestamp = self.generate_timestamp(),
            asset = asset,
        )

        return self.call(
            method = "GET",
            params = params,
            url = url,
        )

    def future_account_balance_v2(
        self,
        url: str = "/fapi/v2/balance",
        recv_window: int = 5_000,
    ) -> dict | None:
        params: dict[str, int] = dict(
            recvWindow = recv_window,
            timestamp = self.generate_timestamp(),
        )

        return self.call(
            method = "GET",
            params = params,
            url = url,
        )

    def account_information_v2(
        self,
        url: str = "/fapi/v2/account",
        recv_window: int = 5_000,
    ) -> dict | None:
        params: dict[str, int] = dict(
            recvWindow = recv_window,
            timestamp = self.generate_timestamp(),
        )

        return self.call(
            method = "GET",
            params = params,
            url = url,
        )

    def get_position_information_v2(
        self,
        url: str = "/fapi/v2/positionRisk",
        symbol: str = "BTCUSDT",
        recv_window: int = 5_000,
    ) -> list[dict | None]:
        params: dict[str, int | float] = dict(
            symbol = symbol,
            recv_window = recv_window,
            timestamp = self.generate_timestamp(),
        )

        return self.call(
            method = "GET",
            url = url,
            params = params,
        )

    # TODO: need to re-implement the function
    def get_current_open_order(
        self,
        url: str = "/fapi/v1/openOrder",
        symbol: str = "BTCUSDT",
        recv_window: int = 5_000,
    ):
        params: dict[str, int | float] = dict(
            symbol = symbol,
            recv_window = recv_window,
            timestamp = self.generate_timestamp()
        )

        return self.call(
            method = "GET",
            url = url,
            params = params,
        )

    def get_all_open_order(
        self,
        url: str = "/fapi/v1/openOrders",
        symbol: str = "BTCUSDT",
        recv_window = 5_000,
    ):
        params: dict[str, int | float] = dict(
            symbol = symbol,
            recv_window = recv_window,
            timestamp = self.generate_timestamp(),
        )

        return self.call(
            method = "GET",
            url = url,
            params = params,
        )


class BinanceWebSocketClient(WebSocketClient):
    def generate_timestamp(self) -> int:
        return int(time.time() * 1_000)

    def __init__(
        self,
        api_key: str,  # Necessary
        secret_key: str,  # Necessary
        name: str = "BINANCE_WEBSOCKET_CLIENT",
        ping_interval: int = 20,
        default_callback: Callable | None = None,
    ) -> None:
        '''
        ;Handle one subscription at a time at the future level
        ;Composition

        ;MarketWebSocketClient
            - public endpoint
        ;UserWebSocketClient
            - private endpoint
        ;TradeWebSocketClient
            - private endpoint
        '''
        super().__init__(name = name if name else "BINANCE_FUTURE_WEBSOCKET_CLIENT")

        # access point of each WebSCoektClient
        self.wss: dict[str, WebSocket] = dict()

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

        return

    def start(self):
        for key in self.wss:
            ws = self.wss[key]
            try:
                ws.start()
                operation_logger.info(
                    f"{__name__} - {self.__class__.__name__} - {self.name} - Successfully started "
                    f"{ws.name if hasattr(ws, 'name') else f'{self.name}_{key.upper()}_WEBSOCKET'}."
                )
            except Exception as e:
                operation_logger.critical(
                    f"{__name__} - {self.__class__.__name__} - {self.name} - Unexpected Error while starting "
                    f"{ws.name if hasattr(ws, 'name') else f'{self.name}_{key.upper()}_WEBSOCKET'}: {str(e)}"
                )

        self._authenticate()
        return

    def _parse_trade_pair(
        self,
        trade_pair: TradePair,
        capitalize: bool = False,
    ) -> str | None:
        if isinstance(trade_pair, TradePair):
            ticker: str = trade_pair.ticker.upper() if capitalize else trade_pair.ticker.lower()
            quote: str = trade_pair.quote.upper() if capitalize else trade_pair.quote.lower()
            return f"{ticker}{quote}"
        return "BTCUSDT" if capitalize else "btcusdt"

    '''
    ####################################################################################
    User Stream
    ####################################################################################
    '''
    def account_position(
        self,
        callback: Callable,
        trade_pair: TradePair | None = None,
        topic: str = "account.position",
    ) -> None:
        self._user_subscribe(callback, topic, trade_pair)
        return

    '''
    ####################################################################################
    Market Stream
    ####################################################################################
    '''
    def agg_trade(
        self,
        callback: Callable,
        trade_pair: TradePair | None = None,
        req_topic: str = "aggTrade",
        push_topic: str = "aggTrade",
    ) -> None:
        '''
        ;func aggTrade
            - Aggregate Trade Streams

        - Request Topic: aggTrade
        - Push Topic: aggTrade
        - Stream e.g.: btcusdt@aggTrade
        '''
        stream: str = f"@{req_topic}"
        self._market_subscribe(stream, push_topic, callback, trade_pair)
        return

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
        contract_type: Union[
            Literal["perpetual"],
            Literal["current_quarter"],
            Literal["next_quarter"],
            Literal["tradifi_perpetual"]
        ] = "perpetual",
        interval: Union[
            Literal["1s"],
            Literal["1m"],
            Literal["3m"],
            Literal["5m"],
            Literal["15m"],
            Literal["30m"],
            Literal["1h"],
            Literal["2h"],
            Literal["4h"],
            Literal["6h"],
            Literal["8h"],
            Literal["12h"],
            Literal["1d"],
            Literal["3d"],
            Literal["1w"],
            Literal["1M"],
        ] = "1s",
        push_topic: str = "continuous_kline",
    ) -> None:
        '''
        ;func kline
            - Continuous Contract Kline Candlestick

        - Request Topic: continuousKline
        - Push Topic: continuous_kline
        - Stream Format: <symbol>_<contract_type>@continuousKline_<interval>
        - Stream e.g.: btcusdt_perpetual@continuousKline_1s
        '''
        stream: str = f"_{contract_type}@{req_topic}_{interval}"
        self._market_subscribe(stream, push_topic, callback, trade_pair)
        return

    def ticker(
        self,
        callback: Callable,
        trade_pair: TradePair | None = None,
        req_topic: str = "ticker",
        push_topic: str = "24hrTicker",
    ) -> None:
        '''
        ;func ticker
        - <symbol>@ticker
        - Individual symbol ticker stream
        - topic: ticker
        - push_topic: 24hrTicker
        '''
        def ticker_callback(msg: dict) -> None:
            symbol: str = msg.get("s", None)
            symbol_ticker: str = symbol[3:]
            symbol_quote: str = symbol[:len(symbol) - 4]
            ticker = Ticker(
                ticker=TradePair(ticker=symbol_ticker, quote=symbol_quote,),
                last_price=float(msg.get('c', 0)),
                timestamp=int(msg.get("E", self.generate_timestamp()))
            )
            callback(ticker)
            return

        stream: str = f"@{req_topic}"
        self._market_subscribe(stream, push_topic, ticker_callback, trade_pair)
        return

    def depth(
        self,
        callback: Callable,
        trade_pair: TradePair | None = None,
        req_topic: str = "bookTicker",
        push_topic: str = "bookTicker",
    ) -> None:
        '''
        ;func depth()
        - <symbol>@bookTicker
        '''
        stream: str = f"@{req_topic}"
        self._market_subscribe(stream, push_topic, callback, trade_pair)
        return

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
            operation_logger.error(
                f"{__name__} - {self.__class__.__name__} - {self.name} - "
                "MarketWebSocketClient is not initialized."
            )
            return

        if not callable(callback):
            operation_logger.error(
                f"{__name__} - {self.__class__.__name__} - {self.name} - "
                f"The provided callback for {stream} is not callable."
            )
            return

        try:
            ws.subscribe(streams=stream, push_topic=push_topic, callback=callback)
        except Exception as e:
            operation_logger.critical(
                f"{__name__} - {self.__class__.__name__} - {self.name} - "
                f"Failed to subscribe to {stream}: {str(e)}"
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
            operation_logger.error(
                f"{__name__} - {self.__class__.__name__} - {self.name} - "
                "UserWebSocketClient is not initialized."
            )
            return

        if not callable(callback):
            operation_logger.error(
                f"{__name__} - {self.__class__.__name__} - {self.name} - "
                f"The provided callback for {stream} is not callable."
            )
            return

        try:
            ws.subscribe(
                callback_function=callback,
                method=stream,
                params=dict(
                    symbol=symbol,
                )
            )
        except Exception as e:
            operation_logger.critical(
                f"{__name__} - {self.__class__.__name__} - {self.name} - "
                f"Failed to subscribe to {stream}: {str(e)}"
            )
        return
