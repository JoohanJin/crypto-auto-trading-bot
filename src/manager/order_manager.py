import time
from object.broker import BrokerRegistry
from object.price import Price
from src.custom_telegram.telegram_bot_class import CustomTelegramBot
from src.object.order import Order
from logger.set_logger import operation_logger
from src.object.trade import TradePair


class OrderManager:
    '''
    - Manage all the order
        - make the trade decision? hmm not sure.
    - Manage all the brokers provided
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
        brokers: BrokerRegistry,  # Brokers Storage
    ) -> None:
        self.brokers: BrokerRegistry = brokers
        self.telegram_bot: CustomTelegramBot = telegram_bot
        return

    def __del__(self: "OrderManager") -> None:
        return

    def order(
        self,
        order: Order,
    ) -> None:
        try:
            # make an order through the broker registry.
            # TODO: implement the broker registry
            self.brokers
        except Exception as e:
            operation_logger.critical(
                f"{__name__} - {self.__class__.__name__} - Error during the Order: {str(e)}"
            )
        return

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
            - will get the list of ticker prices returned from multiple brokers.
        '''
        try:
            return round((sum(prices) / len(prices)), rounding)
        except Exception as e:
            operation_logger.error(
                f"{__name__} - {self.__class__.__name__} - Error while getting the average ticker price: {str(e)}"
            )

    def __get_ticker_current_prices(self) -> list[float]:
        '''
        - func __get_ticker_current_prices()
            - get the list of ticker prices returned from multiple brokers in the OrderManager.

        - Params: None

        - Return:
            - prices: list[float]
        '''
        res = list()

        return res
