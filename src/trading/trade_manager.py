# Standard Library
import threading
import time

# Custom Library
from src.core.models.service_dto import AccountInformation, MarkPrice, Position
from src.integrations.telegram.telegram_bot_class import CustomTelegramBot
from src.infrastructure.logging.set_logger import get_logger, get_adapter
from src.interfaces.pipeline_interface import PipelineController
from src.core.models.score_mapping import ScoreMapper
from src.brokers.binance.http_client import BinanceFutureHttpClient
from src.interfaces.http_interface import HttpInterface

# Core Models
from src.core.models.signal import Signal, TradeSignal
from src.core.models.trade import TradePair, TradeState
from src.core.models.order import Order, Side

logger = get_logger(__name__)


class TradeManager:
    """
    ##########################
    # Static Method
    ##########################
    """
    @classmethod
    def generate_timestamp(cls) -> int:
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
    ######################
    # Class Method
    ######################
    """

    def __init__(
        self,
        signal_pipeline_controller: PipelineController[Signal],
        http_interface: HttpInterface,  # TODO: need to fully move from EachBroker to the Interface
        binance_future_client: BinanceFutureHttpClient,
        delta_mapper: ScoreMapper,
        telegram_bot: CustomTelegramBot,
        trade_pair: TradePair | None = None,
        leverage: int = 10,
        trade_weight: float = 0.1,  # 10% of the total asset
        take_profit_rate: float = 0.2,  # 20% -> to prevent the error
        stop_loss_rate: float = 0.2,  # 20% -> to prevent the error
        score_threashold: int = 2_000,  # 1_000,
        score_trend_management: int = 200,  # 200
        name: str | None = None,
    ) -> None:
        """
        func __init__():
            - initialize the TradeManager with the given signal generator and REST API caller for MexC.
            - initialize the necessary member variables and start the TradeManager.
        """
        self.name: str = name if name else "TRADE_MANAGER"
        self.logger = get_adapter(logger, f"{self.__class__.__name__}_{self.name}")

        # For trading specific logs, we can use the same adapter but maybe with a different level or just use info.
        # However, to keep it consistent with the original design where trading logs went to a different file:
        self.trading_logger = get_adapter(get_logger(__name__, "trading"), f"{self.__class__.__name__}_{self.name}")

        '''
        # TODO: Need to keep the record of the previous order.
        # TODO: Keep checking where that order is still alive or not.
        # TODO: Need to refactor the order layer to get the data from the DTO,
        # order for unified and modular implementation.
        '''
        self.trade_pair: TradePair = (
            trade_pair
            if isinstance(trade_pair, TradePair)
            else TradePair(ticker="BTC", quote="USDT")
        )

        # Set the signal piepline as a member variable
        self.signal_pipeline_controller: PipelineController[Signal] = signal_pipeline_controller

        # For HTTP Communication (RESTful API)
        self.http_interface: HttpInterface = http_interface  # ! Need to use this in the future.
        self.binance_client: BinanceFutureHttpClient = binance_future_client

        self.delta_mapper: ScoreMapper = delta_mapper

        self.telegram_bot: CustomTelegramBot = telegram_bot

        self.score_threshold: int = score_threashold
        self.trend_manager_score: int = score_trend_management  # keep the biased score to keep the current score.

        # TODO_LONG_TERM: decide these variables dynamically
        self.leverage: int = leverage
        self.trade_weight: float = trade_weight
        self.tp_rate: float = take_profit_rate
        self.sl_rate: float = stop_loss_rate

        # Set the thread pool as a member function.
        self.threads: list[threading.Thread] = []

        # Set the trade score as a member variable.
        self.trade_score_lock: threading.Lock = threading.Lock()
        self.trade_score: int = 0

        self.lock_previous_order = threading.Lock()
        self.previous_order: Order | None = None

        # Start the TradeManager
        self.start()

        self.logger.info(
            f"[INIT_COMPLETE] Ready | Pair: {self.trade_pair.ticker}/{self.trade_pair.quote} | "
            f"Leverage: {self.leverage} | Threshold: {self.score_threshold}"
        )
        return

    def __del__(
        self,
    ) -> None:
        """
        func __del__():
            - Destructor is the TradeManager.
            - delete the TradeManager object.
            - need to remove all the threads and possibly dynamic objects as well.
        """
        self.logger.info(
            "[SHUTDOWN] Cleanup initiated | Threads: %d | Score: %d", len(self.threads), self.trade_score
        )
        return

    """
    #########################
    # Multi-Thread Management
    #########################
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
        """
        # Initialize the threads
        self._initialize_threads()

        # Start the threads
        self._start_threads()

        return

    def stop(
        self,
    ) -> None:
        # TODO: Implment the destructor.
        for thread in self.threads:
            thread.stop()
        return

    def _initialize_threads(
        self,
    ) -> None:
        """
        func _initialize_threads():
            - private method
            - It will set up the thread pool for the TradeManager.

        param self:
            - TradeManager object
        """
        # Generate the threads for the function, need to plan it.
        thread_get_signal: threading.Thread = threading.Thread(
            target = self._thread_get_signal,
            name = "Thread-Get-Signal",
        )

        thread_decide_trade: threading.Thread = threading.Thread(
            target = self._thread_decide_trade,
            name = "Thread-Decide-Trade",
        )

        # initialize the threads for the operations
        self.threads.extend([thread_get_signal, thread_decide_trade])
        return

    def _start_threads(
        self,
    ) -> None:
        """
        func _start_threads():
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
                self.logger.info(f"[THREAD_START] {thread.name} | Status: running")

            except RuntimeError as e:  # If there is an error during the runtime
                self.logger.critical(
                    f"[THREAD_ERROR] {thread.name} failed | Error: RuntimeError: {str(e)}"
                )
                raise RuntimeError(
                    f"{__name__}: Failed to start thread '{thread.name}': {str(e)}"
                )

            except Exception as e:  # Unknown Exception
                self.logger.error(f"[THREAD_ERROR] {thread.name} failed | Error: {type(e).__name__}: {str(e)}")
                raise Exception(
                    f"{__name__}: Failed to start thread '{thread.name}': {str(e)}"
                )

        return

    """
    ##########################
    # Signal Management Method
    ##########################
    """
    def _decide_trade(
            self,
            score: int,
    ) -> TradeState:
        """
        func _decide_trade():
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
            previous_order = self.previous_order.copy() if self.previous_order else None

        if (previous_order is not None):  # there is a current order
            # Reverse
            if (
                (score > (self.score_threshold // 2)) and (previous_order.type == Side.SELL)
            ):
                return TradeState.REVERSE_BUY
            if (
                (score < (-1 * (self.score_threshold // 2))) and (previous_order.type == Side.BUY)
            ):
                return TradeState.REVERSE_SELL
        else:  # there is no current order
            if (score > self.score_threshold):
                return TradeState.NEW_BUY
            if (score < (-1 * self.score_threshold)):
                return TradeState.NEW_SELL
        return TradeState.HOLD  # by default it is not doing anything.

    def _construct_new_order(
        self,
        buy_or_sell: TradeState,
    ) -> Order:
        try:
            mark_price: MarkPrice = self._get_mark_price()   # market price

            order_side: Side
            order_side_str: str
            entry_price: float = mark_price.mark_price
            tp_price: float
            sl_price: float
            ticker_size: float
            quote_size: float
            meta_data: dict[str, bool | str] = None

            tp_price, sl_price = self._get_target_prices(
                buy_or_sell = buy_or_sell,
                current_price = entry_price,
            )

            with self.lock_previous_order:
                previous_order = self.previous_order.copy() if self.previous_order else None

            # Determine order side (same for NEW and REVERSE)
            order_side = Side.BUY if buy_or_sell in (2, 8) else Side.SELL
            order_side_str = "BUY" if buy_or_sell in (2, 8) else "SELL"

            # Determine quantities: use REVERSE logic only if reversing AND active position exists
            is_reverse = buy_or_sell in (8, 16) and previous_order is not None

            if is_reverse:
                ticker_size = previous_order.ticker_size * 2
                quote_size = previous_order.quote_size * 2
                meta_data = dict(reverse=True)
            elif buy_or_sell in (2, 4, 8, 16):
                # NEW order (explicitly 2,4 or REVERSE with no active position)
                quote_size = self._get_trade_quote_amt()
                ticker_size = self._get_trade_ticker_amt(entry_price)
                meta_data = dict()
            else:  # Invalid trade state
                raise ValueError(f"Invalid TradeState: {buy_or_sell}")

            return Order(
                side=order_side,
                side_str=order_side_str,
                entry_price=entry_price,
                leverage=self.leverage,  # TODO: Need to dynamically decide the leverage
                tp_price=tp_price,
                sl_price=sl_price,
                trade_pair=self.trade_pair,
                ticker=self.trade_pair.ticker,
                ticker_size=ticker_size,  # TODO: Need to dynamically decide the ticker size rather than fixed ratio
                quote=self.trade_pair.quote,
                quote_size=quote_size,  # TODO: Need to dynamically decide the quote size rather than fixed ratio
                meta_data=meta_data,
            )
        except Exception as e:
            self.logger.critical(
                f"[ORDER_CONSTRUCTION_ERROR] Trade: {buy_or_sell.name if hasattr(buy_or_sell, 'name') else buy_or_sell} | Error: {type(e).__name__}: {str(e)}"
            )
        return

    def _format_trade_message(
        self,
        order: Order,
    ) -> str | None:
        """
        func _format_trade_message():
            - Format trade execution message based on order type
            
        param order: Order
            - The order object with trade details
        param buy_or_sell: TradeState
            - Trade state to determine message suffix
            
        return str | None:
            - Formatted message or None if invalid state
        """
        base_message = (
            f"Trade Signal: {order.side_str}\n"
            f"Entry Price: {order.entry_price}\n"
            f"Amount: {order.quote_size} {order.quote} or {order.ticker_size} {order.ticker}\n"
            f"Take Profit: {order.tp_price}\n"
            f"Stop Loss: {order.sl_price}\n"
        )
        
        if not order.meta_data.get("reverse", False):  # NEW_BUY or NEW_SELL
            return base_message + "It is the new order."
        else:  # REVERSE_BUY or REVERSE_SELL
            return base_message + "It is the reverse order."
        return

    def _make_order(
        self,
        order: Order,
    ) -> None:
        try:
            with self.lock_previous_order:
                self.previous_order = order
            return self.binance_client.order(order=order)
        except Exception as e:
            self.logger.critical(
                f"[ORDER_REGISTRATION_ERROR] Type: {order.side_str } "
                f"| Price: {order.entry_price} | Error: {type(e).__name__}: {str(e)}"
            )
            raise Exception(
                f"{__name__} - {self.__class__.__name__} - Unexpected Error while ordering: {str(e)}"
            ) from e
        return

    def _execute_trade(
        self,
        buy_or_sell: TradeState,
    ) -> None:
        """
        func _execute_trade():
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

            order: Order = self._construct_new_order(buy_or_sell)
            message: str | None = self._format_trade_message(order)

            # order trigger to the telegram bot
            self._make_order(order)
            self.telegram_bot.send_text(message)
            self.trading_logger.info(message)
        except Exception as e:
            self.logger.error(
                f"[TRADE_EXECUTION_ERROR] Trade: {buy_or_sell.name} | Error: {type(e).__name__}: {str(e)}"
            )
            raise Exception
        return
    
    def _thread_decide_trade(
        self,
    ) -> None:
        """
        func _thread_decide_trade():
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

                decision: TradeState = self._decide_trade(
                    score = score,
                )

                if decision in (
                    TradeState.NEW_BUY,
                    TradeState.NEW_SELL,
                    TradeState.REVERSE_BUY,
                    TradeState.REVERSE_SELL
                ):  # can be further improved in the future.
                    # Trade
                    self._execute_trade(
                        buy_or_sell = decision,
                    )

                    # reset the score, but based on the trend
                    # TODO: need to implement more sophisticated one.
                    with self.trade_score_lock:
                        self.trade_score = self.trend_manager_score if decision in (2, 8) else -1 * (self.trend_manager_score)

                time.sleep(0.25)

            except Exception as e:
                self.logger.error(f"[TRADE_DECISION_ERROR] Failed | Score: {score} | Error: {type(e).__name__}: {str(e)}")
        return

    def _thread_get_signal(
        self,
        timestamp_window: int = 5_000,  # for validation purpose
    ) -> None:
        """
        func _thread_get_signal():
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
                signal: TradeSignal = self._get_signal(timestamp_window = timestamp_window,)
                if signal:
                    with self.trade_score_lock:
                        self.trade_score += self._calculate_signal_score_delta(
                            signal_data = signal,
                        )
                        if (self.generate_timestamp() - curr_timestamp > 300_000):
                            self.logger.info(f"[SIGNAL_STATS] Score: {self.trade_score} | Signal Processed")
                            curr_timestamp = self.generate_timestamp()
            except Exception as e:
                self.logger.error(f"[SIGNAL_ERROR] Failed to fetch | Error: {type(e).__name__}: {str(e)}")
        return None

    def _get_signal(
        self,
        timestamp_window: int = 5_000,
    ) -> TradeSignal | None:
        """
        func _get_signal(): private method
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
        return (
            signal_data.signal
            if self.verify_signal(signal_data = signal_data, timestamp_window = timestamp_window)
            else None
        )

    def _calculate_signal_score_delta(
        self,
        signal_data: TradeSignal,
    ) -> int:
        """
        func _calculate_delta():
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
    def _get_current_price(
        self,
    ) -> float | None:
        """
        func _get_current_price():
            - private method
            - get the current price from the MexC API Endpoint.

        param self:
            - TradeManager object

        return float:
            - current price of the asset
        """
        try:
            return self._get_mark_price().mark_price
        except Exception as e:
            self.logger.critical(f"[PRICE_FETCH_ERROR] Mark price unavailable | Error: {type(e).__name__}: {str(e)}")
            raise Exception

    def _get_target_prices(
        self,
        buy_or_sell: TradeState,
        current_price: float,
    ) -> tuple[float, float]:
        """
        func _get_target_prices():
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

    def _decide_to_make_trade(
        self,
    ) -> bool:
        """
        func _decide_to_make_trade():
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
            # positions: list[Position] = self._get_open_orders()  # TODO: need to check with it.
            account_info: AccountInformation = self._get_account_info()

            if (account_info.balance == account_info.available_balance):
                return True
            return False
        except Exception as e:
            self.logger.error(f"[TRADE_DECISION_CHECK_ERROR] Position check failed | Error: {type(e).__name__}: {str(e)}")
            return False

    def _get_trade_quote_amt(
        self,
    ) -> float:
        '''
        ;func _get_trade_amount() -> float
            - return the amt of the money
        '''
        return round(self._get_available_quote() * self.trade_weight, 2)

    def _get_trade_ticker_amt(
        self,
        ticker_price: float,
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
            quote_trade_amt: float = self._get_trade_quote_amt()
            return round((self.leverage * quote_trade_amt) / ticker_price, 3)  # we need the current
        except Exception as e:
            self.logger.critical(f"[QUANTITY_CALC_ERROR] Ticker: {self.trade_pair.ticker} | Price: {ticker_price} | Error: {type(e).__name__}: {str(e)}")
            raise

    def _get_available_quote(self) -> float | None:
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
            # TODO: get the available data.
            # What are we going to do here ? -> get the average from different source of data?
            account_info: AccountInformation = self._get_account_info()
            return round(account_info.available_balance, 4)
        except Exception as e:
            self.logger.critical(f"[BALANCE_FETCH_ERROR] Quote: {self.trade_pair.quote} | Error: {type(e).__name__}: {str(e)}")
            raise

    def _fetch_with_retry(
        self,
        network_call,
        expected_type,
        call_name: str,
        initial_delay: float = 1.0,
    ):
        """
        func _fetch_with_retry():
            - Generic wrapper for network I/O calls with infinite retry logic.
            - Retries indefinitely with exponential backoff until expected type is received.
            - Can be used for any network-based data fetching.

        param self: TradeManager object
        param network_call: Callable
            - Function to call for network I/O (e.g., self.binance_client.get_account_balance)
        param expected_type: type or Callable
            - Expected return type or validation function.
            - If type: checks isinstance(response, expected_type)
            - If callable: calls validation function with response
        param call_name: str
            - Name of the network call for logging purposes
        param initial_delay: float
            - Initial delay in seconds before first retry (default: 1.0)

        return: Object of expected_type or None if never succeeds
        """
        attempt = 0
        delay = initial_delay

        while True:
            try:
                response = network_call()
                
                # Validate response against expected type
                if isinstance(expected_type, type):
                    is_valid = isinstance(response, expected_type)
                else:
                    # expected_type is a callable validation function
                    is_valid = expected_type(response)
                
                if is_valid:
                    if attempt > 0:
                        self.logger.info(
                            f"[SUCCESS] {call_name}() | Attempt: {attempt + 1} | "
                            f"Response Type: {type(response).__name__}"
                        )
                    return response
                
                # Response received but invalid type
                self.logger.warning(
                    f"[INVALID_RESPONSE] {call_name}() | Attempt: {attempt + 1} | "
                    f"Expected: {expected_type.__name__ if hasattr(expected_type, '__name__') else 'callable'} | "
                    f"Got: {type(response).__name__} | "
                    f"Next Retry: {delay:.2f}s"
                )
                time.sleep(delay)
                delay *= 2  # Exponential backoff
                attempt += 1

            except Exception as e:
                self.logger.warning(
                    f"[RETRY] {call_name}() | Attempt: {attempt + 1} | "
                    f"Error: {type(e).__name__}: {str(e)} | "
                    f"Next Retry: {delay:.2f}s"
                )
                time.sleep(delay)
                delay *= 2  # Exponential backoff
                attempt += 1

    def _get_account_info(
        self,
        initial_delay: float = 1.0,
    ) -> AccountInformation:
        """
        func _get_account_info():
            - Fetch account information with infinite retry logic.
            - Uses _fetch_with_retry() for consistent error handling.

        param self: TradeManager object
        param initial_delay: float
            - Initial delay in seconds before first retry (default: 1.0)

        return AccountInformation:
            - Returns AccountInformation once successfully received
        """
        return self._fetch_with_retry(
            network_call=lambda: self.binance_client.get_account_balance(asset=self.trade_pair.quote),
            expected_type=AccountInformation,
            call_name="_get_account_info",
            initial_delay=initial_delay,
        )
    
    def _get_open_orders(
        self,
        initial_delay: float = 1.0,
    ) -> list[Position]:
        """
        func _get_open_orders():
            - Fetch open orders with infinite retry logic.
            - Uses _fetch_with_retry() for consistent error handling.

        param self: TradeManager object
        param initial_delay: float
            - Initial delay in seconds before first retry (default: 1.0)

        return list[Position] | None:
            - Returns list of open orders once successfully received
        """
        return self._fetch_with_retry(
            network_call=lambda: self.binance_client.get_open_orders(symbol=self.trade_pair),
            expected_type=list,
            call_name="_get_open_orders",
            initial_delay=initial_delay,
        )

    def _get_mark_price(
        self,
        initial_delay: float = 1.0,
    ) -> MarkPrice:
        """
        func _get_mark_price():
            - Fetch mark price with infinite retry logic.
            - Uses _fetch_with_retry() for consistent error handling.

        param self: TradeManager object
        param initial_delay: float
            - Initial delay in seconds before first retry (default: 1.0)

        return MarkPrice | None:
            - Returns MarkPrice once successfully received
        """
        return self._fetch_with_retry(
            network_call=lambda: self.binance_client.get_mark_price(symbol=self.trade_pair),
            expected_type=MarkPrice,
            call_name="_get_mark_price",
            initial_delay=initial_delay,
        )


if __name__ == "__main__":
    """
    ####################################################################################################################
    #                          Build TradeManager with all dependencies (no start)                                     #
    #                                                                                                                  #
    # Mimics how SystemManager wires TradeManager. All components are initialized but threads are NOT started.         #
    # User can manually call functions to test if they work.                                                           #
    ####################################################################################################################
    """
    from src.brokers.binance.http_client import BinanceFutureHttpClient
    from unittest.mock import MagicMock, patch
    from dotenv import load_dotenv
    import os

    print("\n" + "="*80)
    print("BUILDING BinanceFutureHttpClient")
    print("="*80 + "\n")

    load_dotenv()

    bak = os.getenv("BINANCE_HMAC_API_KEY")
    bsk = os.getenv("BINANCE_HMAC_SECRET_KEY")

    bfhc = BinanceFutureHttpClient(api_key=bak, secret_key=bsk)

    # =========================================================================
    # 1. Create Pipelines
    # =========================================================================
    print("[1/8] Creating pipelines...")
    from src.pipeline.data_pipeline import DataPipeline
    from src.pipeline.signal_pipeline import SignalPipeline
    
    data_pipeline = DataPipeline()
    signal_pipeline = SignalPipeline()
    print("     ✓ DataPipeline created")
    print("     ✓ SignalPipeline created")

    # =========================================================================
    # 2. Create PipelineControllers
    # =========================================================================
    print("\n[2/8] Creating pipeline controllers...")
    
    signal_pipeline_controller = PipelineController(pipeline=signal_pipeline, name="TEST_SIGNAL_PC")
    print("     ✓ PipelineController[Signal] created")

    # =========================================================================
    # 3. Create ScoreMapper
    # =========================================================================
    print("\n[3/8] Creating score mapper...")
    
    delta_mapper = ScoreMapper()
    print("\n✓ ScoreMapper created")

    # =========================================================================
    # 4. Mock Telegram Bot (avoid env var dependency)
    # =========================================================================
    print("\n[4/8] Setting up telegram bot (mocked)...")
    
    telegram_bot = MagicMock(spec=CustomTelegramBot)
    telegram_bot.send_text = MagicMock(return_value=None)

    api_key = os.getenv("TELEGRAM_API_KEY")
    channel_id = os.getenv("TELEGRAM_CHANNEL_ID")
    telegram_bot = CustomTelegramBot(
        api_key=api_key,
        channel_id=channel_id,
    )
    print("✓ CustomTelegramBot mocked")

    # =========================================================================
    # 6. Build TradeManager with patched start()
    # =========================================================================
    print("\n[6/8] Building TradeManager...\n")
    
    with patch.object(TradeManager, 'start', return_value=None):
        tm = TradeManager(
            signal_pipeline_controller=signal_pipeline_controller,
            http_interface=None,
            binance_future_client=bfhc,
            delta_mapper=delta_mapper,
            telegram_bot=telegram_bot,
            trade_pair=TradePair(ticker="BTC", quote="USDT"),
            leverage=10,
            trade_weight=0.1,
            take_profit_rate=0.10,
            stop_loss_rate=0.05,
            score_threashold=2_000,
            score_trend_management=200,
            name="TEST_TRADE_MANAGER",
        )
        print(tm._get_account_info())

        print(tm._get_open_orders())
        
        mark_price: MarkPrice = tm._get_mark_price()
        print(mark_price)

        print(tm._get_trade_ticker_amt(ticker_price=mark_price.mark_price))

        print(tm._get_trade_quote_amt())

        print(tm._construct_new_order(buy_or_sell=2))  # NEW_BUY
        print(tm._construct_new_order(buy_or_sell=4))  # NEW_SELL
        print(tm._construct_new_order(buy_or_sell=8))  # REVERSE_BUY
        print(tm._construct_new_order(buy_or_sell=16))  # REVERSE_SELL

        print("\n===================== construct order test =========================")
        buy_or_sell: TradeState = TradeState.NEW_BUY
        order: Order = tm._construct_new_order(buy_or_sell)
        print(order, "\n")

        message: str | None = tm._format_trade_message(order)
        print(message)

        res = tm._make_order(order)
        print(res)

        # buy_or_sell: TradeState = TradeState.REVERSE_BUY
        # order: Order = tm._construct_new_order(buy_or_sell)
        # print(order, "\n")

        buy_or_sell: TradeState = TradeState.NEW_SELL
        order: Order = tm._construct_new_order(buy_or_sell)
        print(order, "\n")

        # buy_or_sell: TradeState = TradeState.REVERSE_SELL
        # order: Order = tm._construct_new_order(buy_or_sell)
        # print(order, "\n")

        print("\n===================== trade message test =========================")
        message: str | None = tm._format_trade_message(order)
        print(message)

        # order trigger to the telegram bot
        # async def test_telegram_send_text(msg: str):
        #     await tm.telegram_bot.send_text(message)
        
        # asyncio.run(test_telegram_send_text(message))
        tm.telegram_bot.send_text(message)

        # print("\n===================== make order test =========================")
        # res = tm._make_order(order)
        # print(res)
        # for r in res:
        #     print(r)
        #     print()

    # Replace the binance_client with our mock for get_available_quote()
    print("\n✓ TradeManager instantiated (threads NOT started)")
