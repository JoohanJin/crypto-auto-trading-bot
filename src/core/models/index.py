from enum import IntFlag
import time
from typing import Dict


class IndexType(IntFlag):
    EMA = 1 << 0    # 0001
    SMA = 1 << 1    # 0010
    PRICE = 1 << 2  # 0100


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
    @classmethod
    def generate_timestamp(cls) -> int:
        return int(time.time() * 1_000)

    def __init__(
        self,
        timestamp: int | None,
        index_type: IndexType,
        data: Dict[str, Dict[int, float]],
    ) -> None:
        self.__timestamp: int = timestamp if timestamp else self.generate_timestamp()
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
