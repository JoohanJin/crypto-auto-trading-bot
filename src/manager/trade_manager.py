# Standard Library
import threading
import asyncio
import time
from typing import List, Dict, Tuple

# Custom Library
from custom_telegram.telegram_bot_class import CustomTelegramBot
from logger.set_logger import operation_logger, trading_logger
from mexc.future import FutureMarket as MexCFutureMarket
from binance.future import FutureMarket as BinanceFutureMarket
from object.score_mapping import ScoreMapper
from object.signal import Signal, TradeSignal
from pipeline.signal_pipeline import SignalPipeline
from interface.pipeline_interface import PipelineController


class TradeManager:
    """
    ######################################################################################################################
    #                                               Static Method                                                        #
    ######################################################################################################################
    """

    @staticmethod
    def generate_timestamp() -> int:
        """
        func generate_timestamp(): staticmethod
            - return the timestamp based on the current time in ms
        """
        return int(time.time() * 1000)

    @staticmethod
    def verify_signal(
        signal_data: Signal,
        timestamp_window: int = 5_000,
    ) -> bool:
        """
        func __verify_signal():
            - private method
            - verify the signal based on the timestamp.

        param self: TradeManager object
        param signal_data: TradeSignal object
            - signal data which is passed from the signal pipeline.
        param timestamp_window: int
            - limit for the signal generation timestamp.
            - If the difference between the current timestamp and signal timestamp is greater than the timestamp_window, then it will be ignored.
            - the default value is 5000 ms == 5 seconds.

        return bool:
            - True if the signal is valid, otherwise False
        """
        return (
            TradeManager.generate_timestamp() - signal_data.timestamp < timestamp_window
        )

    """
    ######################################################################################################################
    #                                                Class Method                                                        #
    ######################################################################################################################
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
        take_profit_rate: float = 0.15,  # 15%
        stop_loss_rate: float = 0.05,  # 5%
        score_threashold: int = 2_000,  # 2_000,
        trend_managing_score: int = 200,  # 200
    ) -> None:
        """
        func __init__():
            - initialize the TradeManager with the given signal generator and REST API caller for MexC.
            - initialize the necessary member variables and start the TradeManager.
        """
        self.base_symbol: str = base_symbol
        self.ccy_symbol: str = ccy_symbol

        # Set the signal piepline as a member variable
        self.signal_pipeline_controller: PipelineController[Signal] = signal_pipeline_controller

        # Set the MexC Future Market SDK as a member variable
        # to send the REST API to the MexC API Gateway.
        # TODO: Need to change this to interface. -> FUTURE TODO
        self.mexc_future_market_sdk = mexc_future
        self.binance_future_market = binanace_future

        self.delta_mapper: ScoreMapper = delta_mapper

        self.telegram_bot: CustomTelegramBot = telegram_bot

        self.score_threshold: int = score_threashold
        self.trend_manager_score: int = trend_managing_score

        # Set the thread pool as a member function.
        self.threads: List[threading.Thread] = list()

        # Set the trade score as a member variable.
        self.trade_score_lock: threading.Lock = threading.Lock()
        self.trade_score: int = 0

        self.leverage: int = leverage
        self.trade_amount: float = trade_amount
        self.tp_rate: float = take_profit_rate
        self.sl_rate: float = stop_loss_rate

        self.async_loop = asyncio.new_event_loop()  # only for Telegram Client

        # Start the TradeManager
        self.start()

        operation_logger.info(
            f"{__name__} - TradeManager has been intialized and ready to get the signal"
        )
        return None

    def __del__(
        self: object,
    ) -> None:
        """
        func __del__():
            - Destructor is the TradeManager.
            - delete the TradeManager object.
            - need to remove all the threads and possibly dynamic objects as well.
        """
        operation_logger.info(f"{__name__} - TradeManager has been deleted")
        return

    """
    ######################################################################################################################
    #                                             Multi-Thread Management                                                #
    ######################################################################################################################
    """

    def start(
        self: "TradeManager",
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
        self: "TradeManager",
    ) -> None:
        # TODO: Implment the destructor.
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
    ######################################################################################################################
    #                                             Signal Management Method                                               #
    ######################################################################################################################
    """

    def thread_handle_async_trade_execution(self, loop) -> None:
        """ """
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.__thread_decide_trade())
        return

    def __thread_get_signal(
        self,
        timestamp_window: int = 5000,
    ) -> None:
        """
        func __thread_get_signal():
            - A private method
            - It gets the signal from the signal pipeline
            - This function should be run by other thread which is monitoring the system.

        param self:
            - TradeManager object
        param timestamp_window: int
            - limit for the signal generation timestamp for the signal.
            - If the difference between the current timestamp and signal timestamp is greater than the timestamp_window, then it will be ignored.
        """
        while True:
            try:
                signal: TradeSignal = self.__get_signal(timestamp_window = timestamp_window,)
                if signal:
                    with self.trade_score_lock:
                        self.trade_score += self.__calculate_signal_score_delta(
                            signal_data = signal,
                        )
                        # print(f"now the score is {self.trade_score}")
            except Exception as e:
                operation_logger.error(
                    f"{__name__} - Error while getting the signal: {e}"
                )
        return None

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
            signal = signal_data
        )

    def __get_signal(
        self,
        timestamp_window: int = 5000,
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
        return signal_data.signal if TradeManager.verify_signal(signal_data = signal_data, timestamp_window = timestamp_window) else None

    def __decide_trade(
        self,
        score: int,
    ) -> int:
        """
        func __decide_trade():
            - private method
            - decide the trade based on the score.
            - It will return the decision based on the score.

        param self:
            - TradeManager object
        param score: int
            - score based on the signal data.

        return int:
            # TODO: Change the state to better FSM
            - 1: buy -> 001: 1
            - -1: sell -> 010: 2
            - 0: hold -> 100: 4
            -> else just nothing.
        """
        if (score > self.score_threshold):  # BUY
            return 1
        elif (score < (-1 * self.score_threshold)):  # SELL
            return -1
        return 0  # by default it is not doing anything.

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

                await self.__execute_trade(
                    buy_or_sell = decision,
                )

                if decision != 0:  # can be further improved in the future.
                    # reset the score, but based on the trend
                    #
                    # TODO: need to implement more sophisticated one.
                    with self.trade_score_lock:
                        self.trade_score = self.trend_manager_score if decision == 1 else -1 * (self.trend_manager_score)

                await asyncio.sleep(0.25)

            except Exception as e:
                operation_logger.error(
                    f"{__name__} - Error while deciding the trade: {str(e)}"
                )

        return None

    def __get_current_price(
        self: "TradeManager",
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
            return float(self.binance_future_market.mark_price(symbol = f"{self.base_symbol}{self.ccy_symbol}").get("indexPrice", 0))
        except Exception as e:
            operation_logger.critical(f"{__name__} - Unknown Exception Invoked during fetching the current price: {str(e)}")
            return None

    def __get_target_prices(
        self,
        buy_or_sell: int,
        current_price: float,
    ) -> Tuple[float, float] | None:
        """
        func __get_target_prices():
            - private method
            - get the target prices based on the current price and the signal.
            - It will return the target prices based on the signal.

        param self:
            - TradeManager object
        param buy_or_sell: int
            - 1: buy
            - -1: sell
            - 0: hold, nothing to do with the function.
        param current_price: float
            - current price of the BTC_USDT, i.e., Index Price is used.

        return Tuple[float]:
            - take profit price, stop loss price
        return None:
            - if the signal is not valid, then it will return None.
        """
        if buy_or_sell == 1:  # Long
            return round(current_price * (1 + (self.tp_rate / self.leverage)), 2), round(current_price * (1 - (self.sl_rate / self.leverage)), 2)
        else:  # Short
            return round(current_price * (1 - (self.tp_rate / self.leverage)), 2), round(current_price * (1 + (self.sl_rate / self.leverage)), 2)

    def __get_trade_amount(
        self,
    ) -> float:
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
            currently_holding_order: list[dict | None] = self.binance_future_market.get_position_information_v2()

            if not len(currently_holding_order):
                # No position is currently held, so it's okay to make a trade.
                return True
            else:
                # A position is already open, so do not make another trade.
                return False
        except Exception as e:
            operation_logger.error(f"{__name__} - {self}.__decide_to_make_trade() - Error while deciding to make trade: {str(e)}")
            return False

    async def __execute_trade(
        self,
        buy_or_sell: int,
    ) -> None:
        """
        func __execute_trade():
            - private method
            - execute the trade based on the signal.
            - This function should be run by the other function which is monitoring some schema.

        param self:
            - TradeManager object
        """
        try:
            if buy_or_sell == 1 or buy_or_sell == -1:
                current_price: float = self.__get_current_price()

                tp_price, sl_price = self.__get_target_prices(
                    buy_or_sell = buy_or_sell,
                    current_price = current_price,
                )

                # TODO: interface implement rather than using the instance by itself.
                # for mexc, it is USDT.
                # for binance, it is BTC.
                trade_amount: float = self.get_base_qty(base_asset_price = current_price,)
                order_type: int = 0

                if buy_or_sell == 1:
                    order_type = 1  # Long
                elif buy_or_sell == -1:
                    order_Type = 3  # Short

                # order trigger to the telgram bot
                if self.__decide_to_make_trade():  # make the trade
                    self.binance_future_market.order(
                        sl_price = sl_price,
                        tp_price = tp_price,
                        leverage = self.leverage,
                        symbol_curr_quantity = max(trade_amount, 0.002),
                        side = "BUY" if order_type == 1 else "SELL"
                    )
                    await self.telegram_bot.send_text(
                        f"Trade Signal: {'Buy' if order_type == 1 else 'Sell'}\nEntry Price: {current_price}\nAmount: {trade_amount}\nTake Profit: {tp_price}\nStop Loss: {sl_price}"
                    )
                    trading_logger.info(
                        f"Trade Signal: {'Buy' if order_type == 1 else 'Sell'}\nEntry Price: {current_price}\nAmount: {trade_amount}\nTake Profit: {tp_price}\nStop Loss: {sl_price}"
                    )
                else:
                    trading_logger.info(
                        f"Trade Signal: {'Buy' if order_type == 1 else 'Sell'}\nEntry Price: {current_price}\nAmount: {trade_amount}\nTake Profit: {tp_price}\nStop Loss: {sl_price}\nHowever, the trade has not been occured."
                    )

        except Exception as e:
            operation_logger.error(f"{__name__} - Error while executing the trade: {str(e)}")
        return None

    def get_base_qty(
        self: "TradeManager",
        base_asset_price: float,
    ) -> float | None:
        '''
        - func calculate_btc_qty()
            - calculate the quantity of base crypto:
                - e.g., for BTC_USDT pair, the function is getting the BTC quantity, not the USDT quantity.

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
            margin_amt: float = self.leverage * self.trade_amount * self.get_available_usdt_amt()  # we need the current
            return (margin_amt) / (base_asset_price)
        except Exception as e:
            operation_logger.critical(f"{__name__} - Unknown Exception for Calculating the BTC Amount: {str(e)}")
            return None

    def get_available_usdt_amt(self: "TradeManager", ) -> float | None:
        try:
            account_balances = self.binance_future_market.future_account_balance_v2()

            for balance in account_balances:
                if (balance.get("asset") == "USDT"):
                    return float(balance.get("availableBalance"))
            account_balances = self.binance_future_market.future_account_balance()

            for balance in account_balances:
                if (balance.get("asset") == "USDT"):
                    return balance.get("availableBalance")

        except Exception as e:
            operation_logger.critical(f"{__name__} - {self.binance_future_market} invokes a problem during the user account balance fetch: {str(e)}")
            return None
