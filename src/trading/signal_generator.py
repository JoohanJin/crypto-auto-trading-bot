# TODO: Need to re-plan the structure of Signal generator.
# STANDARD LIBRARY
import json
import threading
import time
from pathlib import Path

# CUSTOM LIBRARY
from src.core.models.index import Index, IndexType
from src.core.models.signal import Signal, TradeSignal
from src.infrastructure.logging.set_logger import get_adapter, get_logger
from src.integrations.telegram.telegram_bot_class import CustomTelegramBot
from src.interfaces.pipeline_interface import PipelineController
from src.strategy.strategy_manager import StrategyManager

logger = get_logger(__name__)


class SignalGenerator:
    """
    ######################################################################################################################
    #                                               Static Method                                                        #
    ######################################################################################################################
    """

    @classmethod
    def generate_timestamp(cls) -> int:
        """
        static func generate_timestamp():
            - Generate the timestamp using the current time, in the form of epoch in ms.

        param None

        return int
            - the timestam in the form of epoch in ms.
        """
        return int(time.time() * 1_000)

    def start_threads(self, threads: list[threading.Thread]) -> None:
        for thread in threads:
            try:
                # start the thread.
                thread.start()
                self.logger.info(f"[THREAD_START] {thread.name} | Status: running")
            except RuntimeError as e:
                self.logger.critical(
                    f"[THREAD_ERROR] {thread.name} failed | Error: {type(e).__name__}: {e!s}"
                )
                raise RuntimeError(f"Failed to start thread '{thread.name}': {e!s}")
            except Exception as e:
                self.logger.critical(
                    f"[THREAD_ERROR] {thread.name} failed | Error: {type(e).__name__}: {e!s}"
                )
                raise Exception(
                    f"Unexpected error starting thread: '{thread.name}': {e!s}"
                )

    """
    ######################################################################################################################
    #                                               Function Method                                                      #
    ######################################################################################################################
    """

    def __init__(
        self,
        data_pipeline_controller: PipelineController[
            dict[str, int | IndexType, dict[int, float]]
        ],
        signal_pipeline_controller: PipelineController[dict[str, int | TradeSignal]],
        custom_telegram_bot: CustomTelegramBot,
        signal_window: int = 2_500,
        name: str | None = None,
        strategy_manager: StrategyManager | None = None,
    ) -> None:
        """
        func __init__():
            - Initialize the Strategy Handler.
            - It gets the pipeline as a parameter for the indicator fetching.
            - It initializes the telegram bot for the notification.
            - It initializes the threads for the indicator fetching.

        param self: StrategyHandler
            - class object
        param pipeline: DataPipeline
            - Data pipeline for the indicator fetching.

        return None
        """
        self.name: str = name if name else "SIGNAL_GENERATOR"
        self.logger = get_adapter(logger, f"{self.__class__.__name__}_{self.name}")

        # data pipeline to get the indicators
        self.data_pipeline_controller: PipelineController[
            dict[str, int | IndexType, dict[int, float]]
        ] = data_pipeline_controller
        self.signal_pipeline_controller: PipelineController[
            dict[str, int | object.TradeSignal]
        ] = signal_pipeline_controller

        # telegram bot manager to send the notification.
        self.__telegram_bot: CustomTelegramBot = custom_telegram_bot

        # Shared Structure
        # Mutex Lock
        self.indicators_lock: threading.Lock = threading.Lock()
        self.indicators: dict[IndexType, Index | None] = {
            IndexType.SMA: None,
            IndexType.EMA: None,
            IndexType.PRICE: None,
            IndexType.VOLATILITY: None,
        }

        self.signal_window: int = signal_window
        # H-L% chop filter threshold — from backtest v2.3 (sliding-window volatility).
        # data_processor computes (max-min)/last_price*100 over 600s sliding window.
        self.volatility_threshold: float = 0.45

        # Override volatility threshold from config/optimized_thresholds.json if available
        self._load_optimized_thresholds()

        # threads pool
        self.threads: list[threading.Thread] = []
        self.strategy_manager: StrategyManager = strategy_manager or StrategyManager(
            indicators=self.indicators,
            indicators_lock=self.indicators_lock,
            push_signal_callback=self.push_signal,
            signal_window=signal_window,
        )

        # Start
        self.start()

        self.logger.info(f"[COMPONENT_INIT] {self.name} | Status: ready")

    def _load_optimized_thresholds(self) -> None:
        """Load volatility_threshold from config/optimized_thresholds.json.
        Falls back to the hardcoded default if the file is missing or malformed."""
        config_path = Path("config") / "optimized_thresholds.json"
        if not config_path.exists():
            self.logger.info(
                "[CONFIG] optimized_thresholds.json not found — using hardcoded volatility_threshold"
            )
            return

        try:
            with open(config_path) as f:
                cfg = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            self.logger.warning(
                f"[CONFIG] Failed to load optimized_thresholds.json: {e} — using defaults"
            )
            return

        if "volatility_threshold" in cfg:
            self.volatility_threshold = float(cfg["volatility_threshold"])

        self.logger.info(
            f"[CONFIG] Loaded optimized_thresholds.json | volatility_threshold={self.volatility_threshold:.4f}"
        )

    def start(self) -> None:
        # initialize the threads
        self._init_threads()
        # start each thread, which is in the threads pool.
        self.start_threads(self.threads)

    """
    ######################################################################################################################
    #                                                 Threads Management                                                 #
    ######################################################################################################################
    """

    def _init_threads(
        self,
    ):
        """
        - func _init_threads:
            - Initialize the threads for the indicator fetching.
            - It will be used to initialize the threads for the indicator fetching.
            - It will be used to consume the data and generate the signals based on the data and pass it to the signal pipeline.

        - param self: StrategyHandler

        - return None
        """
        index_thread: threading.Thread = threading.Thread(
            name="index_data_getter",
            target=self.get_data,
            daemon=True,
        )
        self.logger.info(f"[THREAD_START] {index_thread.name} | Status: ready")

        status_thread: threading.Thread = threading.Thread(
            name="status_logger",
            target=self._thread_log_status,
            daemon=True,
        )
        self.logger.info(f"[THREAD_START] {status_thread.name} | Status: ready")

        self.threads.extend(
            [
                index_thread,
                status_thread,
            ]
        )

    """
    ######################################################################################################################
    #                                      Read Data from the Data Pipeline                                              #
    ######################################################################################################################
    """

    def get_data(
        self,
    ) -> None:
        while True:
            try:
                data: Index = self.data_pipeline_controller.pop(
                    block=True,
                )
                if data:
                    with self.indicators_lock:
                        self.indicators[data.index_type] = data
            except Exception as e:
                self.logger.critical(
                    f"[SIGNAL_ERROR] get_data() | Error: {type(e).__name__}: {e!s}"
                )

    def push_signal(self, signal: Signal) -> None:
        try:
            # 1. Volatility Chop Filter
            final_signal = signal
            volatility_index = self.indicators.get(IndexType.VOLATILITY)

            if volatility_index and volatility_index.data:
                # Use 600s (10 min) window for H-L% volatility — closest to
                # the backtest's 15-min candle. Short windows (10-60s) are too
                # noisy; 600s captures meaningful price swings.
                # Fallback to the longest available period if 600 not present.
                current_volatility = volatility_index.data.get(
                    600, list(volatility_index.data.values())[-1]
                )

                if current_volatility < self.volatility_threshold:
                    self.logger.debug(
                        f"[CHOP_FILTER] Volatility H-L% ({current_volatility:.3f}%) "
                        f"< {self.volatility_threshold:.3f}%. "
                        f"Overriding {signal.signal.name} -> HOLD."
                    )
                    # Override the payload with a HOLD signal, keeping the original timestamp
                    final_signal = Signal(signal=TradeSignal.HOLD, timestamp=signal.timestamp)

            # 2. Push the final signal
            self.signal_pipeline_controller.push(final_signal)
            self.logger.debug(
                f"[SIGNAL_GEN] Signal: {final_signal.signal.name} | Status: success"
            )
        except Exception as e:
            self.logger.critical(
                f"[SIGNAL_ERROR] push_signal() | Error: {type(e).__name__}: {e!s}"
            )

    def _thread_log_status(self) -> None:
        """
        Periodically logs the status of the signal generator,
        including data freshness and potential health issues.

        Purpose:
        - Checks if data pipeline is providing fresh data.
        - Logs staleness of key indicators (SMA, EMA, PRICE).
        - Helps detect pipeline lag or disconnects early.
        """
        while True:
            try:
                time.sleep(60)  # Log every minute

                with self.indicators_lock:
                    status_str = []
                    now = self.generate_timestamp()

                    for idx_type, idx_data in self.indicators.items():
                        if idx_data:
                            freshness = now - idx_data.timestamp
                            status = "FRESH" if freshness < 5000 else "STALE"
                            status_str.append(
                                f"{idx_type.name}: {status} ({freshness}ms ago)"
                            )
                        else:
                            status_str.append(f"{idx_type.name}: NO_DATA")

                    log_msg = f"[STATUS_HEARTBEAT] Indicators: {' | '.join(status_str)}"
                    self.logger.info(log_msg)

            except Exception as e:
                self.logger.error(
                    f"[STATUS_LOG_ERROR] Failed to log status | Error: {type(e).__name__}: {e!s}"
                )
                time.sleep(10)
