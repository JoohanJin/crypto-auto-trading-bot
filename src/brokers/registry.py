import threading

from src.infrastructure.logging.set_logger import get_logger, get_adapter
from src.core.models.broker import Broker

logger = get_logger(__name__)


class BrokerRegistry:
    '''
    - Centralized Broker management with metadata.

    # ! TODO: heap sorted based on the priority.
        -> Top priority at the top of the heap.
    '''
    def __init__(self: "BrokerRegistry", name: str | None = None) -> None:
        self.name: str = name if name else "BROKER_REGISTRY"
        self.logger = get_adapter(logger, f"{self.__class__.__name__}_{self.name}")
        
        self._brokers: dict[str, Broker] = dict()
        self._broker_dict_lock: threading.Lock = threading.Lock()
        return

    def register_broker(self: "BrokerRegistry", broker: Broker) -> None:
        try:
            with self._broker_dict_lock:
                self._brokers[broker.broker_id] = broker
            self.logger.info(f"Broker: {broker.broker_id} has been added to the brokers.")
        except Exception as e:
            self.logger.error(f"Error while registering the broker: {str(e)}")
        return

    def get_broker(self: "BrokerRegistry", broker_id: str) -> Broker | None:
        try:
            with self._broker_dict_lock:
                return self._brokers.get(broker_id, None)
        except Exception as e:
            self.logger.error(f"Error while getting the broker: {str(e)}")
        return

    def enable_broker(self: "BrokerRegistry", broker_id: str) -> None:
        try:
            with self._broker_dict_lock:
                self._brokers.get(broker_id, None).enabled = True
            self.logger.info(f"enabled the Broker: {broker_id}.")
        except Exception as e:
            self.logger.error(f"Error while enabling Broker: {broker_id}: {str(e)}")
        return

    def disable_broker(self: "BrokerRegistry", broker_id: str) -> None:
        try:
            with self._broker_dict_lock:
                self._brokers.get(broker_id, None).enabled = False
            self.logger.info(f"disabled the Broker: {broker_id}.")
        except Exception as e:
            self.logger.error(f"Error while enabling Broker: {broker_id}: {str(e)}")
        return
