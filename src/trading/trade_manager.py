# Standard Library
import json
import threading
import time
from pathlib import Path

from src.brokers.binance.http_client import BinanceFutureHttpClient
from src.core.models.order import Order, Side
from src.core.models.score_mapping import ScoreMapper
# Custom Library
from src.core.models.service_dto import AccountInformation, MarkPrice, Position
# Core Models
from src.core.models.signal import Signal, TradeSignal
from src.core.models.signal_window import SignalWindow
from src.core.models.trade import PositionState, TradePair, TradeState
from src.infrastructure.logging.set_logger import get_adapter, get_logger
from src.integrations.telegram.telegram_bot_class import CustomTelegramBot
from src.interfaces.http_interface import HttpInterface
from src.interfaces.pipeline_interface import PipelineController

logger = get_logger(__name__)


class TradeManager:
    """
    The TradeManager is the 'brain' of the bot, responsible for high-frequency execution
    based on the Weighted Signal Density & Consensus (WSDC) model.

    OPERATIONAL STRATEGY:
    --------------------
    Instead of following single signals (which are often noisy in short timeframes),
    this manager looks for 'signal clusters' or 'bursts'. It assumes that a high
    density of signals in a short window represents a real market move rather than
    an outlier.

    KEY CONCEPTS:
    1. Momentum (10s): The trigger. We look for a burst of signals (Density)
       with high agreement (Consensus) to enter or reverse a trade.
    2. Structural Bias (10m): The backbone. Longer-term signal history provides
       context, preventing entries against the primary short-term trend.
    3. Consensus Model: Weights signals (e.g., LONG_TERM > SHORT_TERM) to
       calculate a percentage of agreement.
    4. Panic Exit: Rapidly liquidates positions if momentum flips against us,
       even if the long-term structural bias is still intact.
    """

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
        trade_weight: float = 0.15,  # 20% of the total asset
        take_profit_rate: float = 0.2,  # 20% -> to prevent the error
        stop_loss_rate: float = 0.2,  # 20% -> to prevent the error
        trade_cooldown_ms: int = 30_000,  # minimum milliseconds between consecutive trades
        name: str | None = None,
        disable_trade: bool = False,
    ) -> None:
        """
        func __init__():
            - initialize the TradeManager with the given signal generator and REST API caller for MexC.
            - initialize the necessary member variables and start the TradeManager.
        """
        self.name: str = name if name else "TRADE_MANAGER"
        self.logger = get_adapter(logger, f"{self.__class__.__name__}_{self.name}")
        self.trading_logger = get_adapter(
            get_logger(__name__, "trading"), f"{self.__class__.__name__}_{self.name}"
        )

        """
        # TODO: Need to keep the record of the previous order.
        # TODO: Keep checking where that order is still alive or not.
        # TODO: Need to refactor the order layer to get the data from the DTO,
        # order for unified and modular implementation.
        """
        self.trade_pair: TradePair = (
            trade_pair
            if isinstance(trade_pair, TradePair)
            else TradePair(ticker="BTC", quote="USDT")
        )

        # Set the signal piepline as a member variable
        self.signal_pipeline_controller: PipelineController[Signal] = (
            signal_pipeline_controller
        )

        # For HTTP Communication (RESTful API)
        self.http_interface: HttpInterface = (
            http_interface  # ! Need to use this in the future.
        )
        self.binance_client: BinanceFutureHttpClient = binance_future_client

        self.delta_mapper: ScoreMapper = delta_mapper

        self.telegram_bot: CustomTelegramBot = telegram_bot

        self.default_trade_cooldown_ms: int = trade_cooldown_ms
        self.trade_cooldown_ms: int = trade_cooldown_ms
        self.last_trade_timestamp: int = 0  # epoch ms of the last executed trade

        # TODO_LONG_TERM: decide these variables dynamically
        self.leverage: int = leverage
        self.trade_weight: float = trade_weight
        self.tp_rate: float = take_profit_rate
        self.sl_rate: float = stop_loss_rate

        self.disable_trade: bool = disable_trade

        self.disable_trade: bool = disable_trade

        # --- Multi-Window Sliding Storage (Modularized) ---
        self.history_window_ms: int = 600_000  # 10 minutes (structural backbone)
        self.mid_term_window_ms: int = self.history_window_ms // 2  # 5 minutes
        self.short_term_window_ms: int = self.history_window_ms // 5  # 2 minutes

        self.window_short = SignalWindow(window_ms=self.short_term_window_ms)
        self.window_mid = SignalWindow(window_ms=self.mid_term_window_ms)
        self.window_struct = SignalWindow(window_ms=self.history_window_ms)

        self.signal_history_lock: threading.Lock = threading.Lock()

        # --- Entry thresholds (require all 3 windows) ---
        # Defaults mirror latest backtest v2.3 (sliding-window volatility).
        self.consensus_short_term_threshold: float = 1.0
        self.consensus_mid_term_threshold: float = 0.50
        self.consensus_threshold: float = 0.78

        self.hold_threshold: float = 0.5

        # --- Exit thresholds (require all 3 windows) ---
        self.exit_short_term_consensus_threshold: float = 0.25
        self.exit_mid_term_threshold: float = 0.25
        self.exit_consensus_threshold: float = 0.98

        # --- use_exit flag from config ---
        self.use_exit: bool = False

        # Override thresholds from config/thresholds.json if available
        self._load_thresholds()

        # Set the thread pool as a member function.
        self.threads: list[threading.Thread] = []

        self.lock_current_position: threading.Lock = threading.Lock()
        self.current_position: PositionState | None = (
            self.binance_client.get_current_position_state(symbol=self.trade_pair)
        )

        # self.signal_cnt: int = 0
        # self.start_time: int

        # Start the TradeManager
        self.start()

        self.logger.info(
            f"[INIT_COMPLETE] Ready | Pair: {self.trade_pair.ticker}/{self.trade_pair.quote} | "
            f"Leverage: {self.leverage} | Window: {self.history_window_ms}ms"
        )

    def _load_thresholds(self) -> None:
        """
        Load entry/exit thresholds from config/thresholds.json.
        Falls back to the hardcoded defaults if the file is missing or malformed.

        Expected JSON keys (all optional — only present keys are overridden):
            consensus_short_term_threshold, consensus_mid_term_threshold,
            consensus_threshold, exit_short_term_consensus_threshold,
            exit_mid_term_threshold, exit_consensus_threshold
        """
        config_path = Path("config") / "thresholds.json"
        if not config_path.exists():
            self.logger.info(
                "[CONFIG] thresholds.json not found — using hardcoded defaults"
            )
            return

        try:
            with open(config_path) as f:
                cfg = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            self.logger.warning(
                f"[CONFIG] Failed to load thresholds.json: {e} — using defaults"
            )
            return

        # --- Entry thresholds ---
        if "consensus_short_term_threshold" in cfg:
            self.consensus_short_term_threshold = float(cfg["consensus_short_term_threshold"])
        if "consensus_mid_term_threshold" in cfg:
            self.consensus_mid_term_threshold = float(cfg["consensus_mid_term_threshold"])
        if "consensus_threshold" in cfg:
            self.consensus_threshold = float(cfg["consensus_threshold"])

        # --- Exit thresholds ---
        if "exit_short_term_consensus_threshold" in cfg:
            self.exit_short_term_consensus_threshold = float(cfg["exit_short_term_consensus_threshold"])
        if "exit_mid_term_threshold" in cfg:
            self.exit_mid_term_threshold = float(cfg["exit_mid_term_threshold"])
        if "exit_consensus_threshold" in cfg:
            self.exit_consensus_threshold = float(cfg["exit_consensus_threshold"])

        # --- use_exit flag ---
        if "use_exit" in cfg:
            self.use_exit = bool(cfg["use_exit"])

        self.logger.info(
            f"[CONFIG] Loaded thresholds.json | "
            f"Entry: short={self.consensus_short_term_threshold:.2f}, "
            f"mid={self.consensus_mid_term_threshold:.2f}, "
            f"struct={self.consensus_threshold:.2f} | "
            f"Exit: short={self.exit_short_term_consensus_threshold:.2f}, "
            f"mid={self.exit_mid_term_threshold:.2f}, "
            f"struct={self.exit_consensus_threshold:.2f} | "
            f"use_exit={self.use_exit}"
        )

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
            f"[SHUTDOWN] Cleanup initiated | Threads: {len(self.threads)} | History Size: {self.window_struct.density}",
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

    def _thread_log_status(
        self,
    ) -> None:
        """
        Logs the current status and key metrics of the TradeManager periodically.

        Purpose:
        - Provides a 'heartbeat' to confirm the manager is active.
        - Monitors critical state: Position, Signal History size, and recent activity (Density).
        - helps diagnose if the bot is 'stuck' or just waiting for signals.
        """
        while True:
            try:
                time.sleep(60)  # Log every 60 seconds

                with self.signal_history_lock:
                    history_size = self.window_struct.density
                    mid_term_density = self.window_mid.density
                    short_term_density = self.window_short.density
                    hold_count = self.window_short._hold_count

                # Re-fetch current position as it might have changed
                with self.lock_current_position:
                    current_pos_state = self.current_position

                pos_status = "None"
                if current_pos_state:
                    pos_status = f"{current_pos_state.side.name} ({current_pos_state.ticker_size:.4f} {self.trade_pair.ticker})"

                self.logger.info(
                    f"[STATUS_HEARTBEAT] Position: {pos_status} | "
                    f"Struct: {history_size} | Mid: {mid_term_density} | Short: {short_term_density} | "
                    f"HOLDs: {hold_count:.0f} | "
                    f"Last Trade: {self.generate_timestamp() - self.last_trade_timestamp if self.last_trade_timestamp else 'N/A'} ms ago"
                )

            except Exception as e:
                self.logger.error(
                    f"[STATUS_LOG_ERROR] Failed to log status | Error: {type(e).__name__}: {e!s}"
                )
                # Avoid excessive error logging if it's a persistent issue
                time.sleep(10)  # Wait a bit before next attempt if logging fails

    def stop(
        self,
    ) -> None:
        """
        Gracefully stop all threads.
        """
        self.logger.info("[SHUTDOWN] Stopping all threads...")
        # Since threads are likely daemon threads or running infinite loops without stop flags,
        # we rely on the main process termination for now.
        # Ideally, we should implement threading.Event based stopping.

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
            target=self._thread_get_signal,
            name="Thread-Get-Signal",
        )

        thread_decide_trade: threading.Thread = threading.Thread(
            target=self._thread_decide_trade,
            name="Thread-Decide-Trade",
        )

        thread_log_status: threading.Thread = threading.Thread(
            target=self._thread_log_status,
            name="Thread-Log-Status",
        )

        # initialize the threads for the operations
        self.threads.extend([thread_get_signal, thread_decide_trade, thread_log_status])

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
                    f"[THREAD_ERROR] {thread.name} failed | Error: RuntimeError: {e!s}"
                )
                raise RuntimeError(
                    f"{__name__}: Failed to start thread '{thread.name}': {e!s}"
                )

            except Exception as e:  # Unknown Exception
                self.logger.error(
                    f"[THREAD_ERROR] {thread.name} failed | Error: {type(e).__name__}: {e!s}"
                )
                raise Exception(
                    f"{__name__}: Failed to start thread '{thread.name}': {e!s}"
                )

    """
    ##########################
    # Signal Management Method
    ##########################
    """

    def _construct_new_order(
        self,
        buy_or_sell: TradeState,
    ) -> Order:
        try:
            mark_price: MarkPrice = self._get_mark_price()  # market price

            order_side: Side
            order_side_str: str
            entry_price: float = mark_price.mark_price
            ticker_size: float
            quote_size: float
            meta_data: dict[str, bool | str] = None

            with self.lock_current_position:
                current_pos = (
                    self.current_position.copy() if self.current_position else None
                )

            # EXIT — close-only order: sell to close LONG, buy to close SHORT.
            # Size = current position size. No TP/SL needed (flat after close).
            if buy_or_sell == TradeState.EXIT:
                if current_pos is None:
                    raise ValueError("EXIT requested but no position to close")
                # Opposite side to close: if we're LONG (BUY), we SELL to close, and vice versa.
                order_side = Side.SELL if current_pos.side == Side.BUY else Side.BUY
                order_side_str = "SELL" if current_pos.side == Side.BUY else "BUY"
                ticker_size = current_pos.ticker_size
                quote_size = current_pos.quote_size

                # Approximate P/L for logging/messaging.
                # Positive = profit, negative = loss.
                if current_pos.side == Side.BUY:  # long
                    pnl_rate = (
                        entry_price - current_pos.entry_price
                    ) / current_pos.entry_price
                else:  # short
                    pnl_rate = (
                        current_pos.entry_price - entry_price
                    ) / current_pos.entry_price

                meta_data = dict(exit=True, pnl_rate=round(pnl_rate, 6))

                return Order(
                    side=order_side,
                    side_str=order_side_str,
                    entry_price=entry_price,
                    leverage=self.leverage,
                    tp_price=0.0,  # no TP for exit — we're going flat
                    sl_price=0.0,  # no SL for exit — we're going flat
                    trade_pair=self.trade_pair,
                    ticker=self.trade_pair.ticker,
                    ticker_size=ticker_size,
                    quote=self.trade_pair.quote,
                    quote_size=quote_size,
                    meta_data=meta_data,
                )

            # TP/SL only needed for NEW and REVERSE orders (not EXIT)
            tp_price, sl_price = self._get_target_prices(
                buy_or_sell=buy_or_sell,
                current_price=entry_price,
            )

            # Determine order side (same for NEW and REVERSE)
            order_side = (
                Side.BUY
                if buy_or_sell in (TradeState.NEW_BUY, TradeState.REVERSE_BUY)
                else Side.SELL
            )
            order_side_str = (
                "BUY"
                if buy_or_sell in (TradeState.NEW_BUY, TradeState.REVERSE_BUY)
                else "SELL"
            )

            # Determine quantities
            is_reverse = (
                buy_or_sell in (TradeState.REVERSE_BUY, TradeState.REVERSE_SELL)
                and current_pos is not None
            )

            if is_reverse:
                # REVERSE order = close current position + open new base position
                # Order size sent to exchange = position_size (close) + base_size (open) = 2x
                # But the actual new position will be base_size (tracked by PositionState)
                base_quote = self._get_trade_quote_amt()
                base_ticker = self._get_trade_ticker_amt(entry_price)
                ticker_size = round(current_pos.ticker_size + base_ticker, 3)
                quote_size = round(current_pos.quote_size + base_quote, 2)
                meta_data = dict(
                    reverse=True,
                    base_ticker_size=base_ticker,
                    base_quote_size=base_quote,
                )
            elif buy_or_sell in (
                TradeState.NEW_BUY,
                TradeState.NEW_SELL,
            ):
                # NEW order (explicitly NEW_* or REVERSE with no active position)
                quote_size = self._get_trade_quote_amt()
                ticker_size = self._get_trade_ticker_amt(entry_price)
                meta_data = dict()
            else:  # Invalid trade state
                raise ValueError(f"Invalid TradeState: {buy_or_sell}")

            return Order(
                side=order_side,
                side_str=order_side_str,
                entry_price=entry_price,
                leverage=self.leverage,
                tp_price=tp_price,
                sl_price=sl_price,
                trade_pair=self.trade_pair,
                ticker=self.trade_pair.ticker,
                ticker_size=ticker_size,
                quote=self.trade_pair.quote,
                quote_size=quote_size,  # TODO: Need to dynamically decide the quote size rather than fixed ratio
                meta_data=meta_data,
            )
        except Exception as e:
            self.logger.critical(
                f"[ORDER_CONSTRUCTION_ERROR] Trade: {buy_or_sell.name if hasattr(buy_or_sell, 'name') else buy_or_sell} | Error: {type(e).__name__}: {e!s}"
            )
            raise e

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
        # EXIT has no TP/SL — show P/L instead
        if order.meta_data.get("exit", False):
            pnl_rate = order.meta_data.get("pnl_rate", 0.0)
            pnl_pct = round(pnl_rate * 100, 2)
            # Leveraged P/L = raw P/L * leverage (reflects actual account impact)
            leveraged_pnl_pct = round(pnl_rate * self.leverage * 100, 2)
            pnl_label = "Profit" if pnl_rate >= 0 else "Loss"
            return (
                f"Trade Signal: EXIT ({order.side_str} to close)\n"
                f"Close Price: {order.entry_price}\n"
                f"Amount: {order.quote_size} {order.quote} or {order.ticker_size} {order.ticker}\n"
                f"Approx {pnl_label}: {pnl_pct}% (x{self.leverage} leverage: {leveraged_pnl_pct}%)\n"
                f"It is an EXIT order."
            )

        base_message = (
            f"Trade Signal: {order.side_str}\n"
            f"Entry Price: {order.entry_price}\n"
            f"Amount: {order.quote_size} {order.quote} or {order.ticker_size} {order.ticker}\n"
            # f"Take Profit: {order.tp_price}\n"
            # f"Stop Loss: {order.sl_price}\n"
        )

        if not order.meta_data.get("reverse", False):  # NEW_BUY or NEW_SELL
            return base_message + "It is a NEW order."
        else:  # REVERSE_BUY or REVERSE_SELL
            return base_message + "It is a REVERSE order."

    def _update_position(
        self,
        order: Order,
        trade_action: TradeState,
    ) -> None:
        """
        Update current_position based on the order that was just placed.
        Stores the BASE position size, not the exchange order size.
        This prevents size explosion on consecutive REVERSE operations.
        """
        if trade_action == TradeState.EXIT:
            with self.lock_current_position:
                self.current_position = None
            return

        with self.lock_current_position:
            # Check if we are adding to an existing position on the same side
            if (
                self.current_position is not None
                and self.current_position.side == order.side
            ):
                total_ticker_size: float = (
                    self.current_position.ticker_size + order.ticker_size
                )
                # Calculate Weighted Average Entry Price
                new_entry_price = (
                    self.current_position.ticker_size / total_ticker_size
                ) * self.current_position.entry_price + (
                    order.ticker_size / total_ticker_size
                ) * order.entry_price
                self.current_position = PositionState(
                    side=self.current_position.side,
                    ticker_size=total_ticker_size,
                    quote_size=self.current_position.quote_size + order.quote_size,
                    entry_price=new_entry_price,
                    timestamp=self.current_position.timestamp,
                )
                return

            if trade_action in (TradeState.REVERSE_BUY, TradeState.REVERSE_SELL):
                # For REVERSE, the actual new position is base_size (not the 2x order sent to exchange)
                base_ticker = order.meta_data.get("base_ticker_size", order.ticker_size)
                base_quote = order.meta_data.get("base_quote_size", order.quote_size)
            else:
                # NEW_BUY or NEW_SELL: order size == position size
                base_ticker = order.ticker_size
                base_quote = order.quote_size

            self.current_position = PositionState(
                side=order.side,
                ticker_size=base_ticker,
                quote_size=base_quote,
                entry_price=order.entry_price,
                timestamp=self.generate_timestamp(),
            )

    def _make_order(
        self,
        order: Order,
        trade_action: TradeState = TradeState.NEW_BUY,
    ) -> None:
        try:
            self._update_position(order, trade_action)
            return self.binance_client.order(order=order)
        except Exception as e:
            self.logger.critical(
                f"[ORDER_REGISTRATION_ERROR] Type: {order.side_str} "
                f"| Price: {order.entry_price} | Error: {type(e).__name__}: {e!s}"
            )
            raise Exception(
                f"{__name__} - {self.__class__.__name__} - Unexpected Error while ordering: {e!s}"
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
            if not self.disable_trade:
                self._make_order(order, trade_action=buy_or_sell)
                self.telegram_bot.send_text(message)
                self.trading_logger.info(message.replace("\n", " "))
            else:
                # Dry run mode: Update internal position state but don't call API
                self._update_position(order, buy_or_sell)
                self.telegram_bot.send_text("[DRY_RUN]\n" + message)
                self.trading_logger.info("[DRY_RUN] " + message.replace("\n", " "))
        except Exception as e:
            self.logger.error(
                f"[TRADE_EXECUTION_ERROR] Trade: {buy_or_sell.name} | Error: {type(e).__name__}: {e!s}"
            )
            raise Exception
        return

    def _analyze_signals(self) -> TradeState:
        """
        Analyze signal history to determine the next trade action using O(1) sliding windows.
        """
        now: int = self.generate_timestamp()

        with self.signal_history_lock:
            # 1. Slide the Windows
            self.window_short.prune(now)
            self.window_mid.prune(now)
            self.window_struct.prune(now)

            # 2. Warm-up & Density Checks
            history_density = self.window_struct.density
            short_term_density = self.window_short.density
            mid_term_density = self.window_mid.density

            if history_density == 0:
                return TradeState.HOLD

            # Require at least 90% of the history window (9 minutes) to be filled
            oldest_ts = self.window_struct.oldest_timestamp
            if oldest_ts and (now - oldest_ts) < (self.history_window_ms * 0.95):
                return TradeState.HOLD

            # Minimum density thresholds
            if history_density < 350 or short_term_density < 70:
                return TradeState.HOLD

            # 3. HOLD Ratio Check (Chop Filter)
            hold_ratio = self.window_short.hold_ratio
            if hold_ratio >= self.hold_threshold:
                self.logger.debug(f"[CHOP_FILTER] HOLD Ratio ({hold_ratio:.0%}) >= 50%. Vetoing trade.")
                return TradeState.HOLD

            # 4. Extract Consensus Metrics
            consensus_short_term = self.window_short.consensus
            consensus_mid_term = self.window_mid.consensus
            consensus_structural = self.window_struct.consensus

        # 5. Logging
        self.logger.debug(
            f"[WSDC_STATS] Short: {consensus_short_term:+.2f} [D={short_term_density}] | "
            f"Mid: {consensus_mid_term:+.2f} [D={mid_term_density}] | "
            f"Struct: {consensus_structural:+.2f} [D={history_density}]"
        )

        with self.lock_current_position:
            current_pos = (
                self.current_position.copy() if self.current_position else None
            )

        def is_buy() -> bool:
            return (
                (consensus_short_term >= self.consensus_short_term_threshold)
                and (consensus_mid_term >= self.consensus_mid_term_threshold)
                and (consensus_structural >= self.consensus_threshold)
            )

        def is_sell() -> bool:
            return (
                (consensus_short_term <= -self.consensus_short_term_threshold)
                and (consensus_mid_term <= -self.consensus_mid_term_threshold)
                and (consensus_structural <= -self.consensus_threshold)
            )

        def is_exit_from_buy() -> bool:
            # Require ALL 3 windows to flip against us — prevents premature exits on normal pullbacks
            return (current_pos.side == Side.BUY) and (
                (consensus_short_term < -(self.exit_short_term_consensus_threshold))
                and (consensus_mid_term < -(self.exit_mid_term_threshold))
                and (consensus_structural < -(self.exit_consensus_threshold))
            )

        def is_exit_from_sell() -> bool:
            # Require ALL 3 windows to flip against us — prevents premature exits on normal pullbacks
            return (current_pos.side == Side.SELL) and (
                (consensus_short_term > self.exit_short_term_consensus_threshold)
                and (consensus_mid_term > self.exit_mid_term_threshold)
                and (consensus_structural > self.exit_consensus_threshold)
            )

        def is_exit() -> bool:
            return is_exit_from_buy() or is_exit_from_sell()

        def is_reversal_buy() -> bool:
            return (current_pos.side == Side.SELL) and (is_buy())

        def is_reversal_sell() -> bool:
            return (current_pos.side == Side.BUY) and (is_sell())

        if current_pos is None:  # NEW Order
            if is_buy():
                return TradeState.NEW_BUY
            elif is_sell():
                return TradeState.NEW_SELL
            return TradeState.HOLD
        elif (
            is_reversal_buy()
        ):  # stronger condition than exit condition: opposite position + buy signal
            return TradeState.REVERSE_BUY
        elif (
            is_reversal_sell()
        ):  # stronger condition than exit condition: oppstie position + sell signal
            return TradeState.REVERSE_SELL
        elif self.use_exit and is_exit():
            return TradeState.EXIT
        return TradeState.HOLD

    def _thread_decide_trade(
        self,
    ) -> None:
        """
        func _thread_decide_trade():
            - private method
            - decide the trade based on the signal history (WSDC model).
        """
        while True:
            try:
                decision: TradeState = self._analyze_signals()

                if decision in (
                    TradeState.NEW_BUY,
                    TradeState.NEW_SELL,
                    TradeState.REVERSE_BUY,
                    TradeState.REVERSE_SELL,
                    TradeState.EXIT,
                ):
                    # Cooldown check
                    if (
                        self.generate_timestamp() - self.last_trade_timestamp
                    ) < self.trade_cooldown_ms:
                        time.sleep(0.25)
                        continue

                    # Execute trade
                    self._execute_trade(buy_or_sell=decision)
                    # update trade_ts for cooldown
                    self.last_trade_timestamp = self.generate_timestamp()

                    # Add dynamic cooldown for Panic Exits (Whipsaw protection)
                    if decision == TradeState.EXIT:
                        self.logger.warning(
                            "[WHIPSAW_PROTECTION] Panic exit triggered! Extending cooldown to 10 minutes."
                        )
                        self.trade_cooldown_ms = (
                            self.history_window_ms
                        )  # Pause for full structural window
                    else:
                        self.trade_cooldown_ms = (
                            self.default_trade_cooldown_ms
                        )  # Restore configured cooldown

                time.sleep(1)

            except Exception as e:
                self.logger.error(
                    f"[TRADE_DECISION_ERROR] Failed | Error: {type(e).__name__}: {e!s}"
                )

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

        # if self.signal_cnt == 0:
        #     self.start_time = self.generate_timestamp()
        # self.signal_cnt += 1

        if isinstance(signal_data, Signal):
            return (
                signal_data.signal
                if self.verify_signal(
                    signal_data=signal_data, timestamp_window=timestamp_window
                )
                else None
            )
        return None

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
        while True:
            try:
                signal: TradeSignal = self._get_signal(
                    timestamp_window=timestamp_window,
                )
                if isinstance(signal, TradeSignal):
                    weight = self.delta_mapper.map(signal)
                    now = self.generate_timestamp()

                    with self.signal_history_lock:
                        self.window_short.add(now, signal, weight)
                        self.window_mid.add(now, signal, weight)
                        self.window_struct.add(now, signal, weight)

                        self.logger.debug(
                            f"[SIGNAL_TRACK] Added: {signal.name} | Struct Density: {self.window_struct.density}"
                        )

            except Exception as e:
                self.logger.error(
                    f"[SIGNAL_ERROR] Failed to fetch | Error: {type(e).__name__}: {e!s}"
                )

    """
    - Execute Trade Utility Function
    """

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
            self.logger.critical(
                f"[PRICE_FETCH_ERROR] Mark price unavailable | Error: {type(e).__name__}: {e!s}"
            )
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
        if buy_or_sell in (TradeState.NEW_BUY, TradeState.REVERSE_BUY):  # Long
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

            if account_info.balance == account_info.available_balance:
                return True
            return False
        except Exception as e:
            self.logger.error(
                f"[TRADE_DECISION_CHECK_ERROR] Position check failed | Error: {type(e).__name__}: {e!s}"
            )
            return False

    def _get_trade_quote_amt(
        self,
    ) -> float:
        """
        ;func _get_trade_amount() -> float
            - return the amt of the money
        """
        return round(self._get_available_quote() * self.trade_weight, 2)

    def _get_trade_ticker_amt(
        self,
        ticker_price: float,
    ) -> float | None:
        # ! need to be moved to the broker logic.
        """
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
        """
        try:
            quote_trade_amt: float = self._get_trade_quote_amt()
            return round(
                (self.leverage * quote_trade_amt) / ticker_price, 3
            )  # we need the current
        except Exception as e:
            self.logger.critical(
                f"[QUANTITY_CALC_ERROR] Ticker: {self.trade_pair.ticker} | Price: {ticker_price} | Error: {type(e).__name__}: {e!s}"
            )
            raise

    def _get_available_quote(self) -> float | None:
        # ! generalization: need to be moved to the broker logic.
        """
        ;func get_available_quote():
            - Calculate the quantity of the quote quantity: default is USDT.
                - e.g., for BTC_USDT pair, the function is getting the USDT quantity.

        ;params self: class object

        ;params float | None:
            - the amount of the quote
        """
        try:
            # TODO: get the available data.
            # What are we going to do here ? -> get the average from different source of data?
            account_info: AccountInformation = self._get_account_info()
            available_balance: float = account_info.balance

            return round(available_balance, 4)
        except Exception as e:
            self.logger.critical(
                f"[BALANCE_FETCH_ERROR] Quote: {self.trade_pair.quote} | Error: {type(e).__name__}: {e!s}"
            )
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
                    f"Error: {type(e).__name__}: {e!s} | "
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
            network_call=lambda: self.binance_client.get_account_balance(
                asset=self.trade_pair.quote
            ),
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
            network_call=lambda: self.binance_client.get_open_orders(
                symbol=self.trade_pair
            ),
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

        param self: TradeeManager object
        param initial_delay: float
            - Initial delay in seconds before first retry (default: 1.0)

        return MarkPrice | None:
            - Returns MarkPrice once successfully received
        """
        return self._fetch_with_retry(
            network_call=lambda: self.binance_client.get_mark_price(
                symbol=self.trade_pair
            ),
            expected_type=MarkPrice,
            call_name="_get_mark_price",
            initial_delay=initial_delay,
        )
