# Standard Library
from queue import Queue, Full, Empty

# Custom Library
from src.infrastructure.logging.set_logger import get_logger, get_adapter
from src.core.models.signal import Signal
from src.pipeline.base_pipeline import BasePipeline  # TODO: Need to define this class in another class

logger = get_logger(__name__)


class SignalPipeline(BasePipeline[Signal]):
    def __init__(self):
        '''
        func __init__:
            - create a Queue of Dict to store indicator
            - Queue has a maximum size of 100 elements to maintain a rolling window of historical indicators.

        queue:
            - indicator_queue: indicator buffer

            data_struct = {
                "indicator": {
                    "timestamp": <int>, int(time.time() * 1000),
                    "signal": object.TradeSignal
                        # 001: for buy
                        # 010: for sell
                        # 100: for hold -> do nothing
                        # Other signals
                }
            }
        '''
        self.logger = get_adapter(logger, self.__class__.__name__)
        self.signal_queue: Queue[Signal] = Queue()
        return

    def push(
        self,
        signal: Signal,
    ) -> bool:
        '''
        func push_indicator:
            - push the indicator to the buffer.
        param self
            - class object
        param indicator
            - indicator got as a parameter to push to the buffer.
            - Dict[str, Dict[str, Any]]
        '''
        try:
            self.signal_queue.put(
                signal,
                block=False,
                timeout=1,
            )
            return True
        except Full:
            self.logger.warning("Indicator Queue is full. Data cannot be added.")
            return False
        except Exception as e:
            self.logger.warning(f"Indicator Queue: Unknown exception has occurred: {str(e)}")
            return False

    def pop(
        self,
        timeout: int | None = None,
        block: bool = True,  # Default is to be blocked
    ) -> Signal | None:
        '''
        func pop_indicator():
            - get the indicator from the buffer.

        param self
            - class object
        param indicator
            - indicator got as a parameter.
            - Dict[str, Dict[str, Any]]
        param timeout
            - the timeout value for getting indicator from the queue.
        param block
            - the boolean value to indicate if the queue is blocked or not when we get the data.

        return bool
            - return indicator if there is a valid indicator.
        '''
        try:
            return self.signal_queue.get(
                block=block,
                timeout=timeout,
            )
        except Empty:
            self.logger.warning("Indicator Queue is empty. Data cannot be added.")
            return None
        except Exception as e:
            self.logger.warning(f"Indicator Queue: Unknown exception has occurred: {str(e)}")
            return None


if __name__ == "__main__":
    print(f"{__name__} - test running.")
