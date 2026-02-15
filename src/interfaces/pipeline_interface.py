from typing import Generic, TypeVar
from src.pipeline.base_pipeline import BasePipeline
import time

from src.infrastructure.logging.set_logger import get_logger, get_adapter

T = TypeVar('T')  # User Defined template
logger = get_logger(__name__)


class PipelineController(Generic[T]):
    '''
    - this class provides the interface for data pipeline push and pull method.
    - based on the principle of Depeency Inversion Principle.
    - Therefore, even when there are some changes on the data pipeline,
        we do not need to change the code for each class.
    '''
    @classmethod
    def generate_timestamp(cls) -> int:
        return int(time.time() * 1000)

    def __init__(
        self,
        pipeline: BasePipeline,  # Upcasting!
        time_window: int = 5_000,  # 5_000ms = 5s
        name: str | None = None,
    ) -> None:
        '''
        func __init__():
            - Get the actual pipeline.
            - Get the push_only variable so that we can add control of the side. (uni-directional)
        '''
        self.name: str = name if name else "PIPELINE_CONTROLLER"
        self.logger = get_adapter(logger, f"{self.__class__.__name__}_{self.name}")
        
        # Let the programmer decides which operation to be used.
        self.pipeline: BasePipeline = pipeline  # ! DataPipeline or SignalPipeline -> Unified Registry?
        self.time_window: int = time_window

        self.logger.info(f"[SERVICE_INIT] {self.name} initialized")
        return

    def push(
        self,
        object: T,  # object
    ) -> bool:
        '''
        '''
        try:
            self.pipeline.push(object)
            return True
        except Exception as e:
            self.logger.warning(
                f"[DATA_ERROR] push() | Error: {type(e).__name__}: {str(e)}"
            )
            return False

    def pop(
        self,
        block: bool = True,
    ) -> T | None:
        '''
        func pop():
            - pop the data from the queue and return it, if it is not None.
        '''
        try:
            data: T | None = self.pipeline.pop(
                block = block,
            )
            if data:
                if self.check_data_validity(data.timestamp):
                    return data

            return None
        except Exception as e:
            # ! raise CustomException
            self.logger.warning(f"[DATA_ERROR] pop() | Error: {type(e).__name__}: {str(e)}")
            raise  # ! raise the custom exception

    def check_data_validity(
        self,
        timestamp: int,
    ) -> bool:
        return ((self.generate_timestamp() - timestamp) < self.time_window)
