# TODO: Need to re-plan the structure of Signal generator.
# STANDARD LIBRARY
import threading
from typing import List
import time

# CUSTOM LIBRARY
from src.core.models.index import Index, IndexType
from src.integrations.telegram.telegram_bot_class import CustomTelegramBot
from src.infrastructure.logging.set_logger import get_logger, get_adapter
from src.core.models.signal import Signal, TradeSignal
from src.interfaces.pipeline_interface import PipelineController
from src.strategy.strategy_manager import StrategyManager

logger = get_logger(__name__)


class SignalGenerator:
    '''
    ######################################################################################################################
    #                                               Static Method                                                        #
    ######################################################################################################################
    '''
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
                self.logger.critical(f"[THREAD_ERROR] {thread.name} failed | Error: {type(e).__name__}: {str(e)}")
                raise RuntimeError(f"Failed to start thread '{thread.name}': {str(e)}")
            except Exception as e:
                self.logger.critical(f"[THREAD_ERROR] {thread.name} failed | Error: {type(e).__name__}: {str(e)}")
                raise Exception(
                    f"Unexpected error starting thread: '{thread.name}': {str(e)}"
                )
        return

    '''
    ######################################################################################################################
    #                                               Function Method                                                      #
    ######################################################################################################################
    '''
    def __init__(
        self,
        data_pipeline_controller: PipelineController[dict[str, int | IndexType, dict[int, float]]],
        signal_pipeline_controller: PipelineController[dict[str, int | TradeSignal]],
        custom_telegram_bot: CustomTelegramBot,
        signal_window: int = 5_000,
        name: str | None = None,
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
        self.data_pipeline_controller: PipelineController[dict[str, int | IndexType, dict[int, float]]] = data_pipeline_controller
        self.signal_pipeline_controller: PipelineController[dict[str, int | object.TradeSignal]] = signal_pipeline_controller

        # telegram bot manager to send the notification.
        self.__telegram_bot: CustomTelegramBot = custom_telegram_bot

        # Shared Structure
        # Mutex Lock
        self.indicators_lock: threading.Lock = threading.Lock()
        self.indicators: dict[IndexType, Index | None] = {
            IndexType.SMA: None,
            IndexType.EMA: None,
            IndexType.PRICE: None,
        }

        self.signal_window: int = signal_window

        # threads pool
        self.threads: List[threading.Thread] = []

        self.strategy_manager: StrategyManager = StrategyManager(
            indicators = self.indicators,
            indicators_lock = self.indicators_lock,
            push_signal_callback = self.push_signal,
            signal_window = signal_window,
        )

        # Start
        self.start()
        
        self.logger.info(f"[COMPONENT_INIT] {self.name} | Status: ready")

        return None

    def start(self) -> None:
        # initialize the threads
        self._init_threads()
        # start each thread, which is in the threads pool.
        self.start_threads(self.threads)
        return

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
            name = 'index_data_getter',
            target = self.get_data,
            daemon = True,
        )
        self.logger.info(f"[THREAD_START] {index_thread.name} | Status: ready")

        self.threads.extend(
            [
                index_thread,
            ]
        )

        return None

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
                data: Index = self.data_pipeline_controller.pop(block = True,)
                if (data):
                    with self.indicators_lock:
                        self.indicators[data.index_type] = data
            except Exception as e:
                self.logger.critical(f"[SIGNAL_ERROR] get_data() | Error: {type(e).__name__}: {str(e)}")

        return

    def push_signal(self, signal: Signal) -> None:
        try:
            self.signal_pipeline_controller.push(signal)
            self.logger.debug(f"[SIGNAL_GEN] Signal: {signal.signal.name} | Status: success")
        except Exception as e:
            self.logger.critical(f"[SIGNAL_ERROR] push_signal() | Error: {type(e).__name__}: {str(e)}")
