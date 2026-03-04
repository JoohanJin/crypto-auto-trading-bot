# Standard Library
import queue

from src.core.models.index import Index

# CUSTOM LIBRARY
from src.infrastructure.logging.set_logger import get_adapter, get_logger
from src.pipeline.base_pipeline import BasePipeline


logger = get_logger(__name__)


class DataPipeline(BasePipeline[Index]):  # TODO: Make the object for th Data object.
    def __init__(
        self,
        name: str | None = None,
    ) -> None:
        '''
        so each of them is just a data object pushed to the queue, not a group of data.

        data_struct = {
            "timestamp" = <int>, # int(time.time() * 1_000)
            "type" = "ema" || "sma",
            "data" = {
                10: <float>,
                30: <float>,
                60: <float>,
                300: <float>,
                600: <float>,
                1_200: <float>,
                1_800: <float>,
            }
        }

        AND

        data_struct = {
            "timestamp" = <int>, # int(time.time() * 1_000)
            "type" = "price",
            "data" = {
                0 = <float>,
            }
        }
        '''
        # inherit the queue and data type in the queue from the base class.
        super().__init__()
        self.name: str = name if name else "DATA_PIPELINE"
        self.logger = get_adapter(logger, f"{self.__class__.__name__}_{self.name}")
        # data buffer, can be added in the future.

        self.logger.info(f"[COMPONENT_INIT] {self.name} | Status: active")


    def push(
        self,
        data: dict[str, int | str | dict[int, float]],
        block: bool = False,
        timeout: int = 1,  # 1 second
    ) -> bool:
        '''
        func push_data:
            - pushes the data to the corresponding queue based on the key.
            - will be used by data fetcher.
        param self
        param key
            - will get the key value for self.queues to seletively push the data into the respective queue.
            - Enum:
                - "test"
                - "sma"
                - "ema"
                - "?"

        param data
            - Tuple[float]

        return bool
            - return True if the operation is successful.
            - return False if the operation is not successful.
        '''
        try:
            self.queue.put(
                data,
                block=block,
                timeout=timeout,
            )
            return True
        except queue.Full:
            self.logger.warning("[DATA_ERROR] push() | Error: Queue is full")
            return False
        except Exception as e:
            self.logger.warning(f"[DATA_ERROR] push() | Error: {type(e).__name__}: {e!s}")
            return False

    def pop(
        self,
        block: bool = True,
        timeout: int | None = None
    ) -> Index:
        '''
        func pop_data():
            - get the data from the queue with the given key.

        param self:
            - class object
        param data:
            - Tuple[float]
        param block:
            - if the thread will be spinning-wait for the data or not.
        param timeout:
            - give the timeout for the data pop.
            - default is None, for non-Time out.

        return bool
            - return data if there is a valid data.
        '''
        try:
            return self.queue.get(block=block, timeout=timeout)
        except queue.Empty:
            self.logger.warning("[DATA_ERROR] pop() | Error: Queue is empty")
            return None
        except Exception as e:
            self.logger.warning(f"[DATA_ERROR] pop() | Error: {type(e).__name__}: {e!s}")
            return None
