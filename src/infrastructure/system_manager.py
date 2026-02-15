# STANDARD LIBRARY
import os
import time
import sys
import threading

# CUSTOM LIBRARY
from src.infrastructure.logging.set_logger import get_logger, get_adapter
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
            self.logger.info("[COMPONENT_INIT] Telegram Bot | Status: ready")

            # Pipeline
            self.data_pipeline: DataPipeline = DataPipeline()
            self.logger.info("[COMPONENT_INIT] DataPipeline | Status: active")
            self.signal_pipline: SignalPipeline = SignalPipeline()
            self.logger.info("[COMPONENT_INIT] SignalPipeline | Status: active")

            # PipelineController
            self.data_pipeline_controller: PipelineController[Index] = PipelineController(
                pipeline = self.data_pipeline
            )
            self.signal_pipeline_controller: PipelineController[Signal] = PipelineController(
                pipeline = self.signal_pipline
            )
            self.logger.info("[COMPONENT_INIT] PipelineControllers | Count: 2 | Status: ready")

            # ScoreMapper
            self.mapper: ScoreMapper = ScoreMapper()
            self.logger.info("[COMPONENT_INIT] ScoreMapper | Status: ready")

            # Service
            # Websocket
            self.websocket_interface: WebSocketInterface = self._construct_ws_interface()
            self.logger.info("[SERVICE_INIT] WebSocketInterface initialized")
            self.http_interface: HttpInterface = self._construct_http_interface()
            self.logger.info("[SERVICE_INIT] HttpInterface initialized")

            '''
            # Main Components
            '''
            self.data_manager: DataManager = DataManager(
                websocket_interface=self.websocket_interface,
                pipeline_controller=self.data_pipeline_controller,
            )

            self.signal_generator: SignalGenerator = SignalGenerator(
                data_pipeline_controller = self.data_pipeline_controller,
                custom_telegram_bot = self.telegram_bot,
                signal_pipeline_controller = self.signal_pipeline_controller,
            )

            # one more classs: trade_manager -> it will have the FutureMarket SDWK
            self.trade_manager: TradeManager = TradeManager(
                signal_pipeline_controller = self.signal_pipeline_controller,
                http_interface=self.http_interface,
                delta_mapper = self.mapper,
                telegram_bot = self.telegram_bot,
            )
            self.logger.info("[COMPONENT_INIT] TradeManager | Status: ready")

            self.logger.info("[SYSTEM_INIT_COMPLETE] Ready | Components: 7 | Status: operational")

        except KeyboardInterrupt:
            self.logger.warning("[SYSTEM_SHUTDOWN] User interrupt signal received | Action: exiting")
            sys.exit(0)
        except Exception as e:
            self.logger.critical(f"[SYSTEM_INIT_ERROR] Initialization failed | Error: {type(e).__name__}: {str(e)}")
            raise Exception(f"Program encounters critical errors.{str(e)}\n Exiting...")

        return

    def start(self) -> None:
        self.logger.info("[SYSTEM_START] Starting main event loop")
        try:
            while not self._stop.is_set():
                time.sleep(0.5)  # Sleep to reduce the cpu usage.
        except KeyboardInterrupt:
            self.logger.warning("[SYSTEM_SHUTDOWN] User interrupt signal received | Action: exiting")
            sys.exit(0)
        except Exception as e:
            self.logger.critical(f"[SYSTEM_RUNTIME_ERROR] Runtime error | Error: {type(e).__name__}: {str(e)}")
            raise Exception(f"System runtime error: {str(e)}") from e
        return

    def stop(self) -> None:
        if self._stop.is_set():
            self.logger.info("[SYSTEM_SHUTDOWN] Already stopped, skipping")
            return
        self.logger.warning("[SYSTEM_SHUTDOWN] Initiating graceful shutdown | Action: stopping")
        self._stop.set()
        # TODO: add the stop for other components (DataManager, SignalGenerator, TradeManager)
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
            raise ValueError(
                "TELEGRAM_API_KEY and TELEGRAM_CHANNEL_ID must be set in environment variables."
            )
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
            self.logger.critical(
                f"[TELEGRAM_INIT_ERROR] Credentials missing | Error: ValueError: {str(e)}"
            )
            return None
        except Exception as e:
            self.logger.critical(
                f"[TELEGRAM_INIT_ERROR] Initialization failed | Error: {type(e).__name__}: {str(e)}"
            )
            return None

    '''
    # MEXC
    '''
    def _get_mexc_future_credentials(self) -> tuple[str, str]:
        try:
            api_key = os.getenv("MEXC_HMAC_API_KEY")
            secret_key = os.getenv("MEXC_HMAC_SECRET_KEY")
            if not api_key or not secret_key:
                self.logger.critical("[CREDENTIAL_ERROR] MEXC Future | Missing: API_KEY or SECRET_KEY")
                raise ValueError("MEXC Future credentials not configured")
            return api_key, secret_key
        except Exception as e:
            self.logger.critical(
                f"[CREDENTIAL_ERROR] MEXC Future | Error: {type(e).__name__}: {str(e)}"
            )
            return None, None

    def _construct_mexc_wsc(self) -> MexcWebSocketClient:
        try:
            api_key, secret_key = self._get_mexc_future_credentials()
            if not api_key or not secret_key:
                return None
            client = MexcWebSocketClient(
                name="MEXC_WEBSOCKET_CLIENT",
                api_key=api_key,
                secret_key=secret_key,
            )
            self.logger.info("[SERVICE_CLIENT_INIT] MEXC WebSocket Client created")
            return client
        except Exception as e:
            self.logger.critical(
                f"[SERVICE_INIT_ERROR] MEXC WebSocket Client failed | Error: {type(e).__name__}: {str(e)}"
            )
            return None

    def _construct_mexc_future(self) -> MexcFutureHttpClient:
        try:
            api_key, secret_key = self._get_mexc_future_credentials()
            if not api_key or not secret_key:
                return None
            client = MexcFutureHttpClient(
                name="MEXC_FUTURE_HTTP_CLIENT",
                api_key=api_key,
                secret_key=secret_key,
            )
            self.logger.info("[SERVICE_CLIENT_INIT] MEXC Future HTTP Client created")
            return client
        except Exception as e:
            self.logger.critical(
                f"[SERVICE_INIT_ERROR] MEXC Future HTTP Client failed | Error: {type(e).__name__}: {str(e)}"
            )
            return None

    '''
    # BINANCE
    '''
    def _get_binance_http_credentials(self) -> tuple[str, str]:
        try:
            api_key: str = os.getenv("BINANCE_HMAC_API_KEY")
            secret_key: str = os.getenv("BINANCE_HMAC_SECRET_KEY")
            if not api_key or not secret_key:
                self.logger.critical("[CREDENTIAL_ERROR] Binance HTTP | Missing: API_KEY or SECRET_KEY")
                raise ValueError("Binance HTTP credentials not configured")
            return api_key, secret_key
        except Exception as e:
            self.logger.critical(
                f"[CREDENTIAL_ERROR] Binance HTTP | Error: {type(e).__name__}: {str(e)}"
            )
        return
    
    def _get_binance_ws_credentials(self) -> tuple[str, str]:
        try:
            api_key: str = os.getenv("BINANCE_ED25519_API_KEY")
            secret_key: str = os.getenv("BINANCE_ED25519_SECRET_KEY")
            if not api_key or not secret_key:
                self.logger.critical("[CREDENTIAL_ERROR] Binance WebSocket | Missing: API_KEY or SECRET_KEY")
                raise ValueError("Binance WebSocket credentials not configured")
            return api_key, secret_key
        except Exception as e:
            self.logger.critical(
                f"[CREDENTIAL_ERROR] Binance WebSocket | Error: {type(e).__name__}: {str(e)}"
            )
        return

    def _construct_binance_future(self) -> BinanceFutureHttpClient:
        try:
            api_key, secret_key = self._get_binance_http_credentials()
            if not api_key or not secret_key:
                return None
            client = BinanceFutureHttpClient(
                name="BINANCE_FUTURE_HTTP_CLIENT",
                api_key=api_key,
                secret_key=secret_key,
            )
            self.logger.info("[SERVICE_CLIENT_INIT] Binance Future HTTP Client created")
            return client
        except Exception as e:
            self.logger.critical(
                f"[SERVICE_INIT_ERROR] Binance Future HTTP Client failed | Error: {type(e).__name__}: {str(e)}"
            )
        return

    def _construct_binance_wsc(self) -> BinanceWebSocketClient:
        try:
            api_key, secret_key = self._get_binance_ws_credentials()
            if not api_key or not secret_key:
                return None
            client = BinanceWebSocketClient(
                name="BINANCE_WEBSOCKET_CLIENT",
                api_key=api_key,
                secret_key=secret_key,
            )
            self.logger.info("[SERVICE_CLIENT_INIT] Binance WebSocket Client created")
            return client
        except Exception as e:
            self.logger.critical(
                f"[SERVICE_INIT_ERROR] Binance WebSocket Client failed | Error: {type(e).__name__}: {str(e)}"
            )
        return
    
    '''
    # Service Interface
    '''
    def _construct_http_client_registry(self, name: str) -> HttpClientRegistry:
        return HttpClientRegistry(name=name)

    def _construct_http_interface(self, name: str | None = None) -> HttpInterface:
        _name: str = name.upper() if name else "HTTP_CLIENT_INTERFACE"
        try:
            hi: HttpInterface = HttpInterface(
                name=_name,
                client_registry=self._construct_http_client_registry(name=f"{_name}_REGISTRY"),
            )
            binance_client = self._construct_binance_future()
            if binance_client:
                hi.push_client(binance_client)
                self.logger.info(f"[SERVICE_INTERFACE] HTTP Interface | Clients registered: 1")
            return hi
        except Exception as e:
            self.logger.critical(
                f"[SERVICE_INIT_ERROR] HTTP Interface failed | Error: {type(e).__name__}: {str(e)}"
            )
            raise
        
    def _construct_ws_client_registry(self, name: str | None) -> WebSocketClientRegistry:
        return WebSocketClientRegistry(
            name=name or "WEBSOCKET_CLIENT_REGISTRY",
        )

    def _construct_ws_interface(self, name: str | None = None) -> WebSocketInterface:
        _name: str = name.upper() if name else "WEBSOCKET_CLIENT_INTERFACE"
        try:
            wi: WebSocketInterface = WebSocketInterface(
                name=_name,
                client_registry=self._construct_ws_client_registry(name=f"{_name}_REGISTRY")
            )
            binance_wsc = self._construct_binance_wsc()
            mexc_wsc = self._construct_mexc_wsc()
            clients_count = 0
            if binance_wsc:
                wi.push_client(binance_wsc)
                clients_count += 1
            if mexc_wsc:
                wi.push_client(mexc_wsc)
                clients_count += 1
            self.logger.info(f"[SERVICE_INTERFACE] WebSocket Interface | Clients registered: {clients_count}")
            return wi
        except Exception as e:
            self.logger.critical(
                f"[SERVICE_INIT_ERROR] WebSocket Interface failed | Error: {type(e).__name__}: {str(e)}"
            )
            raise


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
