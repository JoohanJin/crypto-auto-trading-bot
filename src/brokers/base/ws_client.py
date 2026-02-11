# Built-in Library
from abc import ABC, abstractmethod

# Custom Library
from src.core.models.trade import TradePair


class WebSocketClient(ABC):
    '''
    ;class WebSocketClient
        - Base Class for WebSocket Client for each broker
        - It defines the contract "each WebSocket for Crypto Broker should have"

    ;TradePair List to check the availabilty? -> how to keep updating the TradePair?
    '''
    def __init__(
        self,
        name: str,
    ) -> None:
        self.name: str = name
        return

    @classmethod
    @abstractmethod
    def _parse_trade_pair(cls, trade_pair: TradePair) -> str:
        '''
        ;func _parse_trade_pair()
            - parse the Trade Pair and return the str data type appropriate for each broker
            - e.g., for MEXC: BTCUSDT, for Binance: BTC_USDT
        '''
        return

    '''
    ####################################################################################
    #                                 Market Stream                                    #
    ####################################################################################

    - ticker for the given symbol
    - kline for the given symbol
    - depth for the given symbol
    '''
    @abstractmethod
    def ticker(self) -> None:
        '''
        ;func ticker
            - getting the latest price, best bids and asks for the given contract
            - real time baseis
        '''
        return

    @abstractmethod
    def kline(self) -> None:
        return

    @abstractmethod
    def order_book(self) -> None:
        '''
        ;func depth()
            - return the depth of the market, i.e., Order Book Depth
            - The entire collection of Bids and Asks for the given contract, organized by price.

        ;The market's ability to sustain relatively large market orders without impacting the price of the security.
        ;The list of all pending limit orders waiting to be executed.
        '''
        return

    '''
    ####################################################################################
    #                                 User Stream                                      #
    ####################################################################################

    - Asset
    - Order History
    '''

    '''
    ####################################################################################
    #                                    Trade                                         #
    ####################################################################################

    - Current order
    - Make Order
    - Cancel Order
    '''
