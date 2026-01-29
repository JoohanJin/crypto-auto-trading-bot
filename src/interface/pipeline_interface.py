from typing import Generic, TypeVar
from pipeline.base_pipeline import BasePipeline
from logger.set_logger import operation_logger
import time

T = TypeVar('T')  # User Defined template


class PipelineController(Generic[T]):
    '''
    - this class provides the interface for data pipeline push and pull method.
    - based on the principle of Depeency Inversion Principle.
    - Therefore, even when there are some changes on the data pipeline,
        we do not need to change the code for each class.
    '''
    def generate_timestamp(self) -> int:
        return int(time.time() * 1000)

    def __init__(
        self,
        pipeline: BasePipeline,  # Upcasting!
        time_window: int = 5_000,  # 5_000ms = 5s
    ) -> None:
        '''
        func __init__():
            - Get the actual pipeline.
            - Get the push_only variable so that we can add control of the side. (uni-directional)
        '''
        # Let the programmer decides which operation to be used.
        self.pipeline: BasePipeline = pipeline  # ! DataPipeline or SignalPipeline -> Unified Registry?
        self.time_window: int = time_window

        operation_logger.info(
            f"{__name__} - {self.__class__.__name__} - pipelineController has been generated."
        )
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
            operation_logger.warning(
                f"{__name__} - {self.__class__.__name__} - Unknown Error has "
                f"been occured. Unsuccessful Push from the pipeline interface: {str(e)}"
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
            operation_logger.warning(
                f"{__name__} - {self.__class__.__name__} - Unknown Error has been occured. "
                f"Unsuccessful Pop: {str(e)}"
            )
            raise  # ! raise the custom exception

    def check_data_validity(
        self,
        timestamp: int,
    ) -> bool:
        return ((self.generate_timestamp() - timestamp) < self.time_window)
