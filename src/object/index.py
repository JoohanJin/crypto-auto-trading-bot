import time
from typing import Dict
from object.constants import IndexType


class Index:
    '''
    json-like dictionary object

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
        "type" = <IndexType>,
        "data" = {
            "0" = <float>,
        }
    }
    '''
    @staticmethod
    def generate_timestamp() -> int:
        return int(time.time() * 1_000)

    def __init__(
        self: 'Index',
        timestamp: int,
        index_type: IndexType,
        data: Dict[str, Dict[int, float]],
    ) -> None:
        self.__timestamp: int = timestamp
        self.__index_type: IndexType = index_type
        self.__data: Dict[str, Dict[int, float]] = data
        return

    @property
    def timestamp(self):
        return self.__timestamp

    @property
    def data(self):
        return self.__data

    @property
    def index_type(self):
        return self.__index_type
