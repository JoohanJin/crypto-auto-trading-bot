from enum import IntFlag
import time
from typing import Dict


class IndexType(IntFlag):
    EMA = 1    # 0001
    SMA = 2    # 0010
    PRICE = 4  # 0100


class Index:
    '''
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
        self,
        timestamp: int | None,
        index_type: IndexType,
        data: Dict[str, Dict[int, float]],
    ) -> None:
        self.__timestamp: int = Index.generate_timestamp() if timestamp is None else timestamp
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
