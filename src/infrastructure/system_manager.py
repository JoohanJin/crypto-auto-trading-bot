# STANDARD LIBRARY
import os
import time
import sys
import threading

# CUSTOM LIBRARY
from src.infrastructure.logging.set_logger import get_logger, get_adapter  # Logger and Adapter
from src.integrations.telegram.telegram_bot_class import CustomTelegramBot
from src.data.data_manager import DataManager
from src.trading.signal_generator import SignalGenerator
from src.trading.trade_manager import TradeManager
from src.pipeline.data_pipeline import DataPipeline
from src.pipeline.signal_pipeline import SignalPipeline
from src.interfaces.pipeline_interface import PipelineController
from src.core.models.score_mapping import ScoreMapper
from src.core.models.index import Index
from src.core.models.signal import Signal

# Service
# Interface
from src.interfaces.ws_client_registry import WebSocketClientRegistry
from src.interfaces.http_client_registry import HttpClientRegistry
from src.interfaces.http_interface import HttpInterface
from src.interfaces.websocket_interface import WebSocketInterface

# MEXC
from src.brokers.mexc.http_client import FutureMarket as MexcFutureHttpClient
from src.brokers.mexc.ws_client import MexcWebSocketClient

# BINANCE
from src.brokers.binance.http_client import BinanceFutureHttpClient
from src.brokers.binance.ws_client import BinanceWebSocketClient

# Logger
logger = get_logger(__name__)


class SystemManager:
    def __init__(
        self,
        name: str | None = None,
    ):
        """
        func __init__():
            - Initialize the System Manager.

        param self: SystemManager
            - class object

        return None
        """
        # Initialize Logger Adapter
        self.name: str = name if name else "SYSTEM_MANAGER"

        # Attach logging_adapter to the class.
        self.logger = get_adapter(logger, f"{self.__class__.__name__}_{self.name}")

        self._stop = threading.Event()
        try:
            '''
            # Sub Components
            '''
            # Telegram Bot for Messaging
            self.telegram_bot: CustomTelegramBot = self._set_up_telegram_bot()

            self.data_pipeline: DataPipeline = DataPipeline()
            self.logger.info(f"{self.data_pipeline} has been started.")

            self.signal_pipline: SignalPipeline = SignalPipeline()
            self.logger.info(f"{self.signal_pipline} has been started.")

            self.mapper: ScoreMapper = ScoreMapper()
            self.logger.info(f"{self.mapper} has been started.")

            self.data_pipeline_controller: PipelineController[Index] = PipelineController(
                pipeline = self.data_pipeline
            )
            self.signal_pipeline_controller: PipelineController[Signal] = PipelineController(
                pipeline = self.signal_pipline
            )

            '''
            # Main Components
            '''
            self.data_manager: DataManager = DataManager(
                websocket = self.mexc_ws,
                pipeline_controller = self.data_pipeline_controller,
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

            self.logger.info("SystemManager has been started and completed all the required setup!")

        except KeyboardInterrupt:
            self.logger.info("Program interrupted by user. Exiting...")
            sys.exit(0)
        except Exception as e:
            self.logger.critical("Program encounters critical errors.")
            raise Exception(f"Program encounters critical errors.{str(e)}\n Exiting...")

        return

    def start(self) -> None:
        try:
            while not self._stop.is_set():
                time.sleep(0.5)  # Sleep to reduce the cpu usage.
        except KeyboardInterrupt:
            self.logger.info("Program interrupted by user. Exiting...")
            sys.exit(0)
        except Exception as e:
            self.logger.critical("Program encounters critical errors.")
            raise Exception(f"Program encounters critical errors.{str(e)}\n Exiting...")
        return

    def stop(self) -> None:
        if self._stop.is_set():
            return
        self._stop.set()
        # add the stop for other compponents as well.
    """
    ####################################################################################
    #                                      HELPER Method                               #
    ####################################################################################
    """
    '''
    # TELEGRAM BOT
    '''
    def _get_telegram_credentials(self):
        api_key = os.getenv("TELEGRAM_API_KEY")
        channel_id = os.getenv("TELEGRAM_CHANNEL_ID")
        if not api_key or not channel_id:
            raise ValueError("TELEGRAM_API_KEY and TELEGRAM_CHANNEL_ID must be set in environment variables.")
        return api_key, channel_id

    def _set_up_telegram_bot(
        self,
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
            api_key, channel_id = self._get_telegram_credentials()
            return CustomTelegramBot(
                api_key=api_key,
                channel_id=channel_id,
            )
        except ValueError as e:
            self.logger.critical(f"The Value Error occured: {str(e)}")
            return None
        except Exception as e:
            self.logger.critical(f"The Unknown Error occured: {str(e)}")
            return None

    '''
    # MEXC
    '''
    def _get_mexc_future_credentials(self) -> tuple[str, str]:
        api_key = os.getenv("MEXC_HMAC_API_KEY")
        secret_key = os.getenv("MEXC_HMAC_SECRET_KEY")
        if not api_key or not secret_key:
            raise ValueError("MEXC_API_KEY and MEXC_SECRET_KEY must be set in environment variables.")
        return api_key, secret_key

    def _construct_mexc_wsc(self) -> MexcWebSocketClient:
        api_key, secret_key = self._get_mexc_future_credentials()

        return MexcWebSocketClient(
            name="MEXC_WEBSOCKET_CLIENT",
            api_key=api_key,
            secret_key=secret_key,
        )

    def _construct_mexc_future(self) -> MexcFutureHttpClient:
        api_key, secret_key = self._get_mexc_future_credentials()

        return MexcFutureHttpClient(
            name="MEXC_FUTURE_HTTP_CLIENT",
            api_key=api_key,
            secret_key=secret_key,
        )

    '''
    # BINANCE
    '''
    def _get_binance_http_credentials(self) -> tuple[str, str]:
        try:
            api_key: str = os.getenv("BINANCE_HMAC_API_KEY")
            secret_key: str = os.getenv("BINANCE_HMAC_SECRET_KEY")
            if not api_key or not secret_key:
                # Static methods don't have access to self.logger, so we use the module logger
                self.logger.critical("API_KEY and/or SECRET_KEY is None.")
                raise ValueError
            return api_key, secret_key
        except Exception as e:
            self.logger.critical(
                f"Getting unexpected error during getting the credentials for Binance Future Http Service: {str(e)}"
            )
        return
    
    def _get_binance_ws_credentials(self) -> tuple[str, str]:
        try:
            api_key: str = os.getenv("BINANCE_ED25519_API_KEY")
            secret_key: str = os.getenv("BINANCE_ED25519_SECRET_KEY")
            if not api_key or not secret_key:
                self.logger.critical("API_KEY and/or SECRET_KEY is None")
                raise ValueError
            return api_key, secret_key
        except Exception as e:
            self.logger.critical(
                f"Unnexpected error during getting the credentials for Binance WebSocket Service: {str(e)}"
            )
        return

    def _construct_binance_future(self) -> BinanceFutureHttpClient:
        try:
            api_key, secret_key = self._get_binance_http_credentials()

            return BinanceFutureHttpClient(
                name="BINANCE_FUTURE_HTTP_CLIENT",
                api_key=api_key,
                secret_key=secret_key,
            )
        except Exception as e:
            self.logger.critical(
                f"Unexpected error while getting BinanceFutureHttpClient: {str(e)}"
            )
        return

    def _construct_binance_wsc(self) -> BinanceWebSocketClient:
        try:
            api_key, secret_key = self._get_binance_ws_credentials()
            return BinanceWebSocketClient(
                name="BINANCE_WEBSOCKET_CLIENT",
                api_key=api_key,
                secret_key=secret_key,
            )
        except Exception as e:
            self.logger.critical(
                f"Unexpected error while getting BinanceWebSocketClient: {str(e)}"
            )
        return
    
    '''
    # Service Interface
    '''
    def _construct_http_client_registry(self) -> HttpClientRegistry:
        return HttpClientRegistry(name="HTTP_CLIENT_REGISTRY")

    def _construct_http_interface(self) -> HttpInterface:
        hi: HttpInterface = HttpInterface(
            name="HTTP_CLIENT_INTERFACE",
            client_registry=self._construct_http_client_registry(),
        )
        hi.push_client(self._construct_binance_future())
        return hi
        
    def _construct_ws_client_registry(self) -> WebSocketClientRegistry:
        return WebSocketClientRegistry(
            name="WEBSOCKET_CLIENT_REGISTRY",
        )

    def _construct_ws_interface(self) -> WebSocketInterface:
        wi: WebSocketInterface = WebSocketInterface(
            name="WEBSOCEKT_CLIENT_INTERFACE",
            client_registry=self._construct_ws_client_registry()
        )
        wi.push_client(self._construct_binance_wsc())
        wi.push_client(self._construct_mexc_wsc())
        return wi


"""
########################################################################################
#                                         Code Run                                     #
########################################################################################
"""
if __name__ == "__main__":
    def main():  # to test run the system manager.
        # ! make the start, stop and terminate command for the SystemManager
        SystemManager()

    main()
