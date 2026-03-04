import time
from dataclasses import dataclass, field
from enum import IntFlag


class IndexType(IntFlag):
    EMA = 1 << 0  # 0001
    SMA = 1 << 1  # 0010
    PRICE = 1 << 2  # 0100


@dataclass
class Index:
    """
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
    """

    index_type: IndexType
    data: dict[str, dict[int, float]]
    timestamp: int = field(default_factory=lambda: int(time.time() * 1_000))

    @classmethod
    def generate_timestamp(cls) -> int:
        return int(time.time() * 1_000)
