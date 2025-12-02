from dataclasses import dataclass
import threading
from binance.base_sdk import FutureBase
from object.trade import TradePair
from logger.set_logger import operation_logger


@dataclass
class Broker:
    '''
    - Wrapper class for the Future Manager:
        - MexC
        - Binance
    '''
    broker_id: str
    broker: FutureBase
    enabled: bool = True
    priority: int = 0
    max_leverage: int = 20
    supported_pairs: list[TradePair] = None


class BrokerRegistry:
    '''
    - Centralized Broker management with metadata.

    # ! TODO: heap sorted based on the priority.
        -> Top priority at the top of the heap.
    '''
    def __init__(self: "BrokerRegistry") -> None:
        self._brokers: dict[str, Broker]
        self._lock: threading.Lock = threading.Lock()
        return

    def register_broker(self: "BrokerRegistry", broker: Broker) -> None:
        try:
            with self._lock:
                self._brokers[broker.broker_id] = broker
            operation_logger.info(f"{__name__} - {self.__class__.__name__} - Broker: {broker.broker_id} has been added to the brokers.")
        except Exception as e:
            operation_logger.error(f"{__name__} - {self.__class_.__name__} - Error while registering the broker: {str(e)}")
        return

    def get_broker(self: "BrokerRegistry", broker_id: str) -> FutureBase | None:
        try:
            with self._lock:
                return self._brokers.get(broker_id, None)
        except Exception as e:
            operation_logger.error(f"{__name__} - {self.__class_.__name__} - Error while getting the broker: {str(e)}")
        return

    def enable_broker(self: "BrokerRegistry", broker_id: str) -> None:
        try:
            with self._lock:
                self._brokers.get(broker_id, None).enabled = True
            operation_logger.info(f"{__name__} - {self.__class__.__name__} - enabled the Broker: {broker_id}.")
        except Exception as e:
            operation_logger.error(f"{__name__} - {self.__class_.__name__} - Error while enabling Broker: {broker_id}: {str(e)}")
        return

    def disable_broker(self: "BrokerRegistry", broker_id: str) -> None:
        try:
            with self._lock:
                self._brokers.get(broker_id, None).enabled = False
            operation_logger.info(f"{__name__} - {self.__class__.__name__} - disabled the Broker: {broker_id}.")
        except Exception as e:
            operation_logger.error(f"{__name__} - {self.__class_.__name__} - Error while enabling Broker: {broker_id}: {str(e)}")
        return
