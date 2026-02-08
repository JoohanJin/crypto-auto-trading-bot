# Standard Library
import threading
import asyncio
import time
from typing import List, Tuple

# Custom Library
from src.brokers.binance.http_client import FutureMarket as BinanceFutureMarket
from src.integrations.telegram.telegram_bot_class import CustomTelegramBot
from src.infrastructure.logging.set_logger import operation_logger, trading_logger
from src.brokers.mexc.http_client import FutureMarket as MexCFutureMarket
from src.core.models.score_mapping import ScoreMapper
from src.core.models.signal import Signal, TradeSignal
from src.interfaces.pipeline_interface import PipelineController
from src.core.models.trade import TradePair, TradeState
from src.core.models.order import Order, OrderType

'''
- Get the signal
- modify the score
    - assess the current market status


- TradeManager
- SignalFetcher
- DecisionMaker
'''


class TradeManager:
    """
    ####################################################################################################################
    #                                               Static Method                                                      #
    ####################################################################################################################
    """
    def generate_timestamp(self) -> int:
        """
        func generate_timestamp():
            - return the timestamp based on the current time in ms
        """
        return int(time.time() * 1_000)

    def verify_signal(
        self,
        signal_data: Signal,
        timestamp_window: int = 5_000,
    ) -> bool:
        """
        func verify_signal():
            - verify the signal based on the timestamp.

        param self: TradeManager object
        param signal_data: TradeSignal object
            - signal data which is passed from the signal pipeline.
        param timestamp_window: int
            - limit for the signal generation timestamp.
            - If the difference between the current timestamp and signal timestamp is greater than the timestamp_window,
                - then it will be ignored.
            - the default value is 5000 ms == 5 seconds.

        return bool:
            - True if the signal is valid, otherwise False
        """
        return (self.generate_timestamp() - signal_data.timestamp) < timestamp_window

    """
    ####################################################################################################################
    #                                                Class Method                                                      #
    ####################################################################################################################
    """

    def __init__(
        self,
        signal_pipeline_controller: PipelineController[Signal],
        mexc_future: MexCFutureMarket,  # TODO: Change this to the interface
        binanace_future: BinanceFutureMarket,  # TODO: Change this to the interface.
        delta_mapper: ScoreMapper,
        telegram_bot: CustomTelegramBot,
        base_symbol: str = "BTC",
        ccy_symbol: str = "USDT",
        leverage: int = 10,
        trade_amount: float = 0.1,  # 10% of the total asset
        take_profit_rate: float = 0.2,  # 20% -> to prevent the error
        stop_loss_rate: float = 0.2,  # 20% -> to preven the error
        score_threashold: int = 2_000,  # 1_000,
        score_trend_management: int = 200,  # 200
    ) -> None:
        """
        func __init__():
            - initialize the TradeManager with the given signal generator and REST API caller for MexC.
            - initialize the necessary member variables and start the TradeManager.
        """
        # TODO: Need to keep the record of the previous order.
        # TODO: Keep checking where that order is still alive or not.
        '''
        # TODO: Need to refactor the order layer to get the data from the DTO,
        # order for unified and modular implementation.
        '''
        self.trade_pair: TradePair = TradePair(ticker = base_symbol, quote = ccy_symbol)

        # Set the signal piepline as a member variable
        self.signal_pipeline_controller: PipelineController[Signal] = signal_pipeline_controller

        # Set the MexC Future Market SDK as a member variable
        # to send the REST API to the MexC API Gateway.
        # TODO: Need to change this to interface.
        self.mexc_future_market_sdk = mexc_future
        self.binance_future_market = binanace_future

        self.delta_mapper: ScoreMapper = delta_mapper

        self.telegram_bot: CustomTelegramBot = telegram_bot

        self.score_threshold: int = score_threashold
        self.trend_manager_score: int = score_trend_management  # keep the biased score to keep the current score.

        # Set the thread pool as a member function.
        self.threads: List[threading.Thread] = list()

        # Set the trade score as a member variable.
        self.trade_score_lock: threading.Lock = threading.Lock()
        self.trade_score: int = 0

        self.leverage: int = leverage
        self.trade_amount: float = trade_amount
        self.tp_rate: float = take_profit_rate
        self.sl_rate: float = stop_loss_rate

        self.async_loop: asyncio.new_event_loop = asyncio.new_event_loop()  # only for Telegram Client

        self.lock_previous_order = threading.Lock()
        self.previous_order: Order | None = None

        # Start the TradeManager
        self.start()

        operation_logger.info(
            f"{__name__} - TradeManager has been intialized and ready to get the signal"
        )
        return None

    def __del__(
        self,
    ) -> None:
        """
        func __del__():
            - Destructor is the TradeManager.
            - delete the TradeManager object.
            - need to remove all the threads and possibly dynamic objects as well.
        """
        operation_logger.info(f"{__name__} - {self.__class__.__name__} - TradeManager has been deleted")
        return

    """
    ####################################################################################################################
    #                                             Multi-Thread Management                                              #
    ####################################################################################################################
    """

    def start(
        self,
    ) -> None:
        """
        func start():
            - start the TradeManager
            - It will initialize the threads and start the threads.
            - make it as a public so that in the future, it will be started at the outside of the class.

        param self:
            - TradeManager object

        return None:
            - it is a void function.
        """
        # Initialize the threads
        self.__initialize_threads()

        # Start the threads
        self.__start_threads()

        return None

    def stop(
        self,
    ) -> None:
        # TODO: Implment the destructor.
        for thread in self.threads:
            thread.stop()
        return

    def __initialize_threads(
        self,
    ) -> None:
        """
        func __initialize_threads():
            - private method
            - It will set up the thread pool for the TradeManager.

        param self:
            - TradeManager object
        """
        # Generate the threads for the function, need to plan it.
        thread_get_signal: threading.Thread = threading.Thread(
            target = self.__thread_get_signal,
            name = "Thread-Get-Signal",
        )

        thread_decide_trade: threading.Thread = threading.Thread(
            target = self.thread_handle_async_trade_execution,
            name = "Thread-Decide-Trade",
            args = (self.async_loop,),
        )

        # initialize the threads for the operations
        self.threads.extend([thread_get_signal, thread_decide_trade])
        return None

    def __start_threads(
        self,
    ) -> None:
        """
        func __start_threads():
            - private method
            - It will start the thread pool for the TradeManager.

        param self:
            - TradeManager object

        return None:
            - it is a void function.
        """
        for thread in self.threads:
            try:  # try this first
                thread.start()
                operation_logger.info(
                    f"{__name__} - Thread {thread.name} has been started"
                )

            except RuntimeError as e:  # If there is an error during the runtime
                operation_logger.critical(
                    f"{__name__}: Failed to start thread '{thread.name}': {str(e)}"
                )
                raise RuntimeError(
                    f"{__name__}: Failed to start thread '{thread.name}': {str(e)}"
                )

            except Exception as e:  # Unknown Exception
                operation_logger.error(
                    f"{__name__} - Unknown Error while starting the threads: {e}"
                )
                raise Exception(
                    f"{__name__}: Failed to start thread '{thread.name}': {str(e)}"
                )

        return None

    """
    ####################################################################################################################
    #                                             Signal Management Method                                             #
    ####################################################################################################################
    """
    def thread_handle_async_trade_execution(self, loop) -> None:
        """ """
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.__thread_decide_trade())
        return

    async def __thread_decide_trade(
        self,
    ) -> None:
        """
        func __thread_decide_trade():
            - private method
            - decide the trade based on the signal.
            - This function should be run by the other function which is monitoring some schema.

        param self:
            - TradeManager object

        return None:
        """
        while True:
            try:
                with self.trade_score_lock:
                    score: int = self.trade_score

                decision: int = self.__decide_trade(
                    score = score,
                )

                if decision in (2, 4, 6, 8):  # can be further improved in the future.
                    # Trade
                    await self.__execute_trade(
                        buy_or_sell = decision,
                    )

                    # reset the score, but based on the trend
                    # TODO: need to implement more sophisticated one.
                    with self.trade_score_lock:
                        self.trade_score = self.trend_manager_score if decision in (2, 8) else -1 * (self.trend_manager_score)

                await asyncio.sleep(0.25)

            except Exception as e:
                operation_logger.error(
                    f"{__name__} - Error while deciding the trade: {str(e)}"
                )

        return None

    def __decide_trade(
        self,
        score: int,
    ) -> TradeState:
        """
        func __decide_trade():
            - private method
            - decide the trade based on the score.
            - It will return the decision based on the score.

        param self:
            - TradeManager object
        param score: int
            - score based on the signal data.

        return TradeState:
            - HOLD = 1
            - NEW_BUY = 2
            - NEW_SELL = 4
            - REVERSE_BUY = 8
            - REVERSE_SELL = 16
        """
        with self.lock_previous_order:
            previous_order = self.previous_order.copy()

        if (previous_order is not None):  # there is a current order
            # Reverse
            if (
                (score > (self.score_threshold // 2)) and (previous_order.type == OrderType.SELL)
            ):
                return TradeState.REVERSE_BUY
            if (
                (score < (-1 * (self.score_threshold // 2))) and (previous_order.type == OrderType.BUY)
            ):
                return TradeState.REVERSE_SELL
        else:  # there is no current order
            if (score > self.score_threshold):
                return TradeState.NEW_BUY
            if (score < (-1 * self.score_threshold)):
                return TradeState.NEW_SELL
        return TradeState.HOLD  # by default it is not doing anything.

    def __construct_new_order(
        self,
        buy_or_sell: TradeState,
    ) -> Order:
        try:
            with self.lock_previous_order:
                previous_order = self.previous_order.copy()

            order_type: OrderType
            order_type_str: str
            entry_price: float = self.__get_current_price()
            tp_price: float
            sl_price: float
            ticker_size: float
            quote_size: float
            meta_data: dict[str, bool | str] = None

            tp_price, sl_price = self.__get_target_prices(
                buy_or_sell = buy_or_sell,
                current_price = entry_price,
            )

            if buy_or_sell in (2, 4):  # NEW
                order_type = OrderType.BUY if buy_or_sell == 2 else OrderType.SELL
                order_type_str = "BUY" if buy_or_sell == 2 else "SELL"

                quote_size = self.get_available_quote()
                ticker_size = self.get_ticker_qty(entry_price, quote_size)
            elif buy_or_sell in (8, 16):  # REVERSE
                order_type = OrderType.BUY if buy_or_sell == 8 else OrderType.SELL
                order_type_str = "BUY" if buy_or_sell == 8 else "SELL"

                ticker_size = previous_order.ticker_size * 2
                quote_size = previous_order.quote_size * 2

                meta_data = dict(
                    reverse = True
                )
            else:  # HOLD or other flipped-bit signal
                raise ValueError(f"Invalid TradeState: {buy_or_sell}")

            return Order(
                type=order_type,
                type_str=order_type_str,
                entry_price=entry_price,
                leverage=self.leverage,  # TODO: Need to dynamically decide the leverage
                tp_price=tp_price,
                sl_price=sl_price,
                ticker=self.trade_pair.ticker,  # TODO: Need to dynamically decide the leverage
                ticker_size=ticker_size,
                quote=self.trade_pair.quote,  # TODO: Need to dynamically decide the leverage
                quote_size=quote_size,
                meta_data=meta_data,
            )
        except Exception as e:
            error_msg: str = f"{__name__} - {self.__class__.__name__} - Error while building the order object: {str(e)}"
            operation_logger.critical(
                error_msg
            )
            raise Exception(
                error_msg
            ) from e

    async def __execute_trade(
        self,
        buy_or_sell: TradeState,
    ) -> None:
        """
        func __execute_trade():
            - private method
            - execute the trade based on the signal.
            - This function should be run by the other function which is monitoring some schema.

        param self:
            - TradeManager object

        return None:
        """
        try:
            if buy_or_sell == TradeState.HOLD:
                return None

            order: Order = self.__construct_new_order(buy_or_sell)

            if buy_or_sell in (2, 4):  # make the trade
                message = (
                    f"Trade Signal: {order.type_str}\n"
                    f"Entry Price: {order.entry_price}\n"
                    f"Amount: {order.quote_size} {order.quote}\n"
                    f"Take Profit: {order.tp_price}\n"
                    f"Stop Loss: {order.sl_price}\n"
                    f"It is the new order."
                )
            elif buy_or_sell in (8, 16):
                message = (
                    f"Trade Signal: {order.type_str}\n"
                    f"Entry Price: {order.entry_price}\n"
                    f"Amount: {order.quote_size} {order.quote}\n"
                    f"Take Profit: {order.tp_price}\n"
                    f"Stop Loss: {order.sl_price}\n"
                    f"It is the reverse order."
                )
            else:  # bitflip error (never know)
                return None

            # order trigger to the telgram bot
            self.__make_order(order)
            await self.telegram_bot.send_text(message)
            trading_logger.info(message)
        except Exception as e:
            operation_logger.error(
                f"{__name__} - {self.__class__.__name__} - Error while executing the trade: {str(e)}"
            )
            raise Exception
        return None

    def __make_order(
        self,
        order: Order,
    ) -> None:
        try:
            # TODO: change this to the broker registry so that just passing
            # order, i.e., DTO, is enough
            self.binance_future_market.order(
                sl_price=order.sl_price,
                tp_price=order.tp_price,
                leverage=order.leverage,
                symbol_curr_quantity=order.ticker_size,
                side=order.type_str,
            )

            with self.lock_previous_order:
                self.previous_order = order
        except Exception as e:
            operation_logger.critical(
                f"{__name__} - {self.__class__.__name__} - Unexpected Error while ordering: {str(e)}"
            )
            raise Exception(
                f"{__name__} - {self.__class__.__name__} - Unexpected Error while ordering: {str(e)}"
            ) from e
        return None

    def __thread_get_signal(
        self,
        timestamp_window: int = 5_000,  # for validation purpose
    ) -> None:
        """
        func __thread_get_signal():
            - A private method
            - It gets the signal from the signal pipeline
            - This function should be run by other thread which is monitoring the system.

        param timestamp_window: int
            - limit for the signal generation timestamp for the signal.
            - If the difference between the current timestamp and signal timestamp is greater
                than the timestamp_window, then it will be ignored.

        return None:
        """
        curr_timestamp = 0
        while True:
            try:
                signal: TradeSignal = self.__get_signal(timestamp_window = timestamp_window,)
                if signal:
                    with self.trade_score_lock:
                        self.trade_score += self.__calculate_signal_score_delta(
                            signal_data = signal,
                        )
                        if (self.generate_timestamp() - curr_timestamp > 300_000):
                            operation_logger.info(
                                f"{__name__} - The current score is {self.trade_score}"
                            )
                            curr_timestamp = self.generate_timestamp()
            except Exception as e:
                operation_logger.error(
                    f"{__name__} - Error while getting the signal: {str(e)}"
                )
        return None

    def __get_signal(
        self,
        timestamp_window: int = 5_000,
    ) -> TradeSignal | None:
        """
        func __get_signal(): private method
            - get the signal from the signal pipeline
            - This function should be run by other thread which is monitoring the system.

        param self:
            - TradeManager object

        return TradeSignal:
            - it will return the parameter signal and decide the action based on the signal.
        return None
            - if the signal is not valid, then it will return None.
        """
        signal_data: Signal = self.signal_pipeline_controller.pop()
        return signal_data.signal if self.verify_signal(
            signal_data = signal_data,
            timestamp_window = timestamp_window
        ) else None

    def __calculate_signal_score_delta(
        self,
        signal_data: TradeSignal,
    ) -> int:
        """
        func __calculate_delta():
            - private method
            - calculate the delta based on the signal data.
            - It will return the delta value based on the signal data.

        param self:
            - TradeManager object
        param signal_data: TradeSignal
            - signal data which is passed from the signal pipeline.

        return int:
            - delta value based on the signal data.
        """
        return self.delta_mapper.map(
            signal = signal_data,
        )

    '''
    - Execute Trade Utility Function
    '''
    def __get_current_price(
        self,
    ) -> float | None:
        """
        func __get_current_price():
            - private method
            - get the current price from the MexC API Endpoint.

        param self:
            - TradeManager object

        return float:
            - current price of the asset
        """
        try:
            return round(
                float(
                    # TODO: need to decouple the TradeManager from the self.binance_future_market
                    self.binance_future_market.mark_price(
                        symbol = f"{self.trade_pair.ticker}{self.trade_pair.quote}"
                    ).get("indexPrice", 0)
                ),
                2,
            )
        except Exception as e:
            operation_logger.critical(
                f"{__name__} - Unknown Exception Invoked during fetching the current price: {str(e)}"
            )
            raise Exception

    def __get_target_prices(
        self,
        buy_or_sell: TradeState,
        current_price: float,
    ) -> Tuple[float, float]:
        """
        func __get_target_prices():
            - private method
            - get the target prices based on the current price and the signal.
            - It will return the target prices based on the signal.

        param self:
            - TradeManager object
        param buy_or_sell: TradeState
            - NEW_BUY (2), REVERSE_BUY (8): Long position
            - NEW_SELL (4), REVERSE_SELL (16): Short position
        param current_price: float
            - current price of the BTC_USDT, i.e., Index Price is used.

        return Tuple[float, float]:
            - (take_profit_price, stop_loss_price)
        """
        if buy_or_sell in (2, 8):  # Long
            return round(
                current_price * (1 + (self.tp_rate / self.leverage)),
                2,
            ), round(
                current_price * (1 - (self.sl_rate / self.leverage)),
                2,
            )
        else:  # Short
            return round(
                current_price * (1 - (self.tp_rate / self.leverage)),
                2,
            ), round(
                current_price * (1 + (self.sl_rate / self.leverage)),
                2,
            )

    def __get_trade_amount(
        self,
    ) -> float:
        '''
        obsolete function but wil be use din the future.
        '''

        open_amount_response: dict = self.mexc_future_market_sdk.asset(
            currency = "USDT",
        )

        if open_amount_response.get("success"):
            return (
                open_amount_response.get("data").get("availableOpen") * self.trade_amount
            )
        else:
            raise Exception(
                f"{__name__} - Error while getting the trade amount: {open_amount_response}"
            )
        return

    def __decide_to_make_trade(
        self,
    ) -> bool:
        """
        func __decide_to_make_trade():
            - private method
            - decide whether to make the trade or not.
            - It will return True if there is an order/orders held by the account.
            - To make sure that only one order can be made at one moment.

        param self:
            - TradeManager object

        return bool:
            - if there is no order held, then we will make an order.
                - return True
            - if there is an order held, then we will not make an order.
                - return False
        """
        try:
            # currently_holding_order: Dict = self.mexc_future_market_sdk.current_position()
            currently_holding_order: list[dict | None] = self.binance_future_market.get_all_open_order()

            # It will check if there is a currently opened order.
            if not len(currently_holding_order):  # if it is 0 then it will make a new order.
                # No position is currently held, so it's okay to make a trade.
                # By default, there is one position in Binance to indicate current isolation mode
                # and leverage with 0 margin in it.
                return True
            else:
                # A position is already open, so do not make another trade.
                return False
        except Exception as e:
            operation_logger.error(
                f"{__name__} - {self}.__decide_to_make_trade() - Error while deciding to make trade: {str(e)}"
            )
            return False

    def get_ticker_qty(
        self,
        ticker_price: float,
        available_quote: float,
    ) -> float | None:
        # ! need to be moved to the broker logic.
        '''
        ;func calculate_btc_qty()
            - calculate the quantity of ticker quantity: default is BTC
                - e.g., for BTC_USDT pair, the function is getting the BTC quantity.

        ;params self: class object
            - TradeManager class instance

        ;params ticker_price: float
            - current price of the ticker.

        ;params: avaialble_quote: float
            - currently available quote.

        ;return flaot | None:
            - the amount of the ticker based on the available quote.

        - need two data:
            - the current BTC price in USDT.
            - the margin value in USDT.
        - The BTC quantity formula would be as follow:
            - (leverage * USDT) / BTC_price
        -> what data do we need to fetch?
            - leverage: the instance field variable.
            - current amount of USDT
                - from the broker
            - weight for the margin value:
                - predefined by the programmer and saved as the field instance.
                - e.g., 10% of the entire balance.
            - The current BTC price.
                - from the broker
        '''
        try:
            margin_amt: float = self.leverage * self.trade_amount * available_quote  # we need the current
            return max(round((margin_amt) / (ticker_price), 3), 0.002)  # upto three significant digits for the BTC quantity
        except Exception as e:
            operation_logger.critical(
                f"{__name__} - {self.__class__.__name__} - Unknown Exception for Calculating the BTC Amount: {str(e)}"
            )
            return None

    def get_available_quote(self) -> float | None:
        # ! generalization: need to be moved to the broker logic.
        '''
        ;func get_available_quote():
            - Calculate the quantity of the quote quantity: default is USDT.
                - e.g., for BTC_USDT pair, the function is getting the USDT quantity.

        ;params self: class object

        ;params float | None:
            - the amount of the quote
        '''
        try:
            account_balances = self.binance_future_market.future_account_balance_v2()

            for balance in account_balances:
                if (balance.get("asset") == self.trade_pair.quote):
                    return float(balance.get("availableBalance"))
            account_balances = self.binance_future_market.future_account_balance()

            for balance in account_balances:
                if (balance.get("asset") == self.trade_pair.quote):
                    return balance.get("availableBalance")

        except Exception as e:
            operation_logger.critical(f"{__name__} - {self.__class__.__name__} - Unexpected Error: {str(e)}")
            return None
