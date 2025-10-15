# STANDARD LIBRARY
import os
import time
import sys
from dotenv import load_dotenv
import threading

# CUSTOM LIBRARY
from custom_telegram.telegram_bot_class import CustomTelegramBot
from manager.data_collector_and_processor import DataCollectorAndProcessor, IndexFactory
from manager.signal_generator import SignalGenerator
from manager.trade_manager import TradeManager
from pipeline.data_pipeline import DataPipeline
from logger.set_logger import operation_logger
from pipeline.signal_pipeline import SignalPipeline
from interface.pipeline_interface import PipelineController
from object.constants import IndexType
from object.score_mapping import ScoreMapper
from object.indexes import Index
from object.signal import Signal

# MEXC
from mexc.future import FutureMarket as MexcFutureMarket, FutureWebSocket as MexcFutureWebSocket

# BINANCE
from binance.future import FutureMarket as BinanceFutureMarket


class SystemManager:
    # @log_decorator
    def __init__(
        self: "SystemManager",
    ):
        """
        func __init__():
            - Initialize the System Manager.

        param self: SystemManager
            - class object

        return None
        """
        try:
            self._stop = threading.Event()

            self.telegram_bot: CustomTelegramBot = self.__set_up_telegram_bot()

            # prepare the necessary parts for injection.
            self.mexc_ws: MexcFutureWebSocket = SystemManager.__construct_mexc_ws()
            operation_logger.info(f"{__name__} - {self.mexc_ws} has been initialized successfully.")

            self.mexc_future: MexcFutureMarket = SystemManager.__construct_mexc_future()
            operation_logger.info(f"{__name__} - {self.mexc_ws} has been initialized successfully.")

            self.binance_future: BinanceFutureMarket = SystemManager.__construct_binance_future()
            operation_logger.info(f"{__name__} - {self.binance_future} has been initialized successfully.")

            self.data_pipeline: DataPipeline = DataPipeline()
            operation_logger.info(f"{self.data_pipeline} has been started.")

            self.signal_pipline: SignalPipeline = SignalPipeline()
            operation_logger.info(f"{self.signal_pipline} has been started.")

            self.mapper: ScoreMapper = ScoreMapper()
            operation_logger.info(f"{self.mapper} has been started.")

            self.data_pipeline_controller: PipelineController[Index] = PipelineController(pipeline = self.data_pipeline)
            self.signal_pipeline_controller: PipelineController[Signal] = PipelineController(pipeline = self.signal_pipline)

            self.data_collector_processor: DataCollectorAndProcessor = (
                DataCollectorAndProcessor(
                    pipeline_controller = self.data_pipeline_controller,
                    websocket = self.mexc_ws,  # use MEXC API Endpoint for Real-Time Data Fetching.
                )
            )

            self.signal_generator: SignalGenerator = SignalGenerator(
                data_pipeline_controller = self.data_pipeline_controller,
                custom_telegram_bot = self.telegram_bot,
                signal_pipeline_controller = self.signal_pipeline_controller,
            )

            # one more classs: trade_manager -> it will have the FutureMarket SDWK
            self.trade_manager: TradeManager = TradeManager(
                signal_pipeline_controller = self.signal_pipeline_controller,
                mexc_future = self.mexc_future,
                binanace_future = self.binance_future,
                delta_mapper = self.mapper,
                telegram_bot = self.telegram_bot,
            )

            # Start working
            while True:
                time.sleep(0.5)  # Sleep to reduce the cpu usage.
        except KeyboardInterrupt:
            operation_logger.info("Program interrupted by user. Exiting...")
            sys.exit(0)
        except Exception as e:
            operation_logger.critical(
                f"{__name__} - Program encounters critical errors."
            )
            raise Exception(f"Program encounters critical errors.{str(e)}\n Exiting...")  # ! raise the custom Exceptions.

        return

    def start(self: "SystemManager") -> None:
        try:
            while not self._stop.is_set():
                time.sleep(0.5)  # Sleep to reduce the cpu usage.
        except KeyboardInterrupt:
            operation_logger.info("Program interrupted by user. Exiting...")
            sys.exit(0)
        except Exception as e:
            operation_logger.critical(
                f"{__name__} - Program encounters critical errors."
            )
            raise Exception(f"Program encounters critical errors.{str(e)}\n Exiting...")
        return

    def stop(self: "SystemManager") -> None:
        if self._stop.is_set():
            return
        self._stop.set()
        # add the stop for other compponents as well.
    """
    ######################################################################################################################
    #                                                Static Method                                                       #
    ######################################################################################################################
    """
    def __set_up_telegram_bot(
        self: "SystemManager",
    ) -> CustomTelegramBot | None:
        """
        func __set_up_telegram_bot():
            - Set up the telegram bot with credentials from environment variables.

        param self: SystemManager
            - class object

        return CustomTelegramBot
            - CustomTelegramBot object
        """
        try:
            api_key, channel_id = SystemManager.__get_telegram_credentials()
            return CustomTelegramBot(
                api_key = api_key,
                channel_id = channel_id,
            )
        except ValueError as e:
            operation_logger.critical(f"{__name__} - The Value Error occured: {str(e)}")
            return None
        except Exception as e:
            operation_logger.critical(f"{__name__} - The Unknown Error occured: {str(e)}")
            return None

    @staticmethod
    def __get_telegram_credentials():
        api_key = os.getenv("TELEGRAM_API_KEY")
        channel_id = os.getenv("TELEGRAM_CHANNEL_ID")
        if not api_key or not channel_id:
            raise ValueError("TELEGRAM_API_KEY and TELEGRAM_CHANNEL_ID must be set in environment variables.")
        return api_key, channel_id

    @staticmethod
    def __get_mexc_future_credentials():
        api_key = os.getenv("MEXC_API_KEY")
        secret_key = os.getenv("MEXC_SECRET_KEY")
        if not api_key or not secret_key:
            raise ValueError("MEXC_API_KEY and MEXC_SECRET_KEY must be set in environment variables.")
        return api_key, secret_key

    @staticmethod
    def __get_binance_future_credentials():
        try:
            api_key: str = os.getenv("BINANCE_API_KEY")
            secret_key: str = os.getenv("BINANCE_SECRET_KEY")
            if not api_key or not secret_key:
                operation_logger.critica(f"{__name__} - API_KEY and/or SECRET_KEY is None.")
                raise ValueError

            return api_key, secret_key
        except Exception as e:
            operation_logger.critica(f"{__name__} - Getting unexpected error during getting the credentials for Binance Future: {str(e)}")

    @staticmethod
    def __construct_mexc_ws() -> MexcFutureWebSocket:
        api_key, secret_key = SystemManager.__get_mexc_future_credentials()

        return MexcFutureWebSocket(
            api_key = api_key,
            secret_key = secret_key,
        )

    @staticmethod
    def __construct_mexc_future() -> MexcFutureMarket:
        api_key, secret_key = SystemManager.__get_mexc_future_credentials()

        return MexcFutureMarket(
            api_key = api_key,
            secret_key = secret_key,
        )

    @staticmethod
    def __construct_binance_future() -> BinanceFutureMarket:
        try:
            api_key, secret_key = SystemManager.__get_binance_future_credentials()

            return BinanceFutureMarket(
                api_key = api_key,
                secret_key = secret_key,
            )
        except ValueError as e:
            operation_logger.critical(f"{__name__} - binance_api_key or/and binance_secret_key is/are None.")


def main():  # to test run the system manager.
    # ! make the start, stop and terminate command for the SystemManager
    main_system_manager: SystemManager = SystemManager()


"""
######################################################################################################################
#                                                     Code Run                                                       #
######################################################################################################################
"""
if __name__ == "__main__":
    main()
