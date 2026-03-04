import time

from src.core.models.order import Order
from src.core.models.price import Price
from src.core.models.trade import TradePair
from src.infrastructure.logging.set_logger import get_adapter, get_logger
from src.integrations.telegram.telegram_bot_class import CustomTelegramBot
from src.interfaces.http_interface import HttpInterface


logger = get_logger(__name__)


class OrderManager:
    '''
    - Manage all the order
        - make the trade decision? hmm not sure.
    - Manage all the clients provided
    '''
    @staticmethod
    def __get_curr_timestamp() -> int:
        # only for internal usage
        return int(time.time() * 1_000)

    '''
    ##############################################################################
    #                                 Class Method                               #
    ##############################################################################
    '''
    def __init__(
        self,
        telegram_bot: CustomTelegramBot,
        clients: HttpInterface,  # Http Client Interface
        name: str | None = None,
    ) -> None:
        self.name: str = name if name else "ORDER_MANAGER"
        self.logger = get_adapter(logger, f"{self.__class__.__name__}_{self.name}")
        self.clients: HttpInterface = clients
        self.telegram_bot: CustomTelegramBot = telegram_bot

        self.logger.info(f"[COMPONENT_INIT] {self.name} | Status: ready")

    def __del__(self) -> None:
        self.logger.info(f"[SHUTDOWN] {self.name} cleanup initiated")

    def order(
        self,
        order: Order,
    ) -> None:
        try:
            # make an order through the client registry.
            self.clients  # TODO: implement the broker registry
        except Exception as e:
            self.logger.critical(f"[TRADE_EXECUTION_ERROR] Order failed | Error: {type(e).__name__}: {e!s}")

    def get_ticker_current_price(
        self,
        trading_pair: TradePair,
    ) -> dict[str, float]:
        '''
        - Return the current price of the given ticker and quote currency.
        dict = {
            "timestamp": <timestamp_in_ms_int>,
            "ticker": "BTC",
            "quote": "USDT",
            "price": <price_of_ticker_float>
        }
        '''
        return Price(
            timestamp=OrderManager.__get_curr_timestamp(),
            trading_pair=trading_pair,
            # price = self.__get_average_ticker_price(
            #   self.__get_ticker_current_prices(),
            # ),
        )

    def __get_average_ticker_price(
        self,
        prices: list[float],
        rounding: int = 2,  # can be dynamic with the Factory method.
    ) -> float:
        '''
        - can use numpy for faster and more accurate result
        - func __get_average_ticker_price()
            - calculate the average value of the floats in the list passed as a parameter
            - return the average value in the float format.

        - params:
            - prices: list[float]
                - list of floats
            - rounding: int
                - precision for the rounding of the given float in the decimals.

        - return:
            - float
                - average value of the values in the param
            - will get the list of ticker prices returned from multiple clients.
        '''
        try:
            return round((sum(prices) / len(prices)), rounding)
        except Exception as e:
            self.logger.error(f"[TRADE_DECISION_ERROR] Average price calculation failed | Error: {type(e).__name__}: {e!s}")

    def __get_ticker_current_prices(self) -> list[float]:
        '''
        - func __get_ticker_current_prices()
            - get the list of ticker prices returned from multiple clients in the OrderManager.

        - Params: None

        - Return:
            - prices: list[float]
        '''
        res = []

        return res
