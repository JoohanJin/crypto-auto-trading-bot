import time
from typing import Dict

from src.core.models.index import Index, IndexType


class IndexFactory:
    '''
    # factory which generates the Index data type.
    # what does it do?
        # check the validity of index Dict?
        # generate the timestamp?
    '''
    @staticmethod
    def generate_timestamp() -> int:
        return int(time.time() * 1_000)

    def __init__(
        self: "IndexFactory",
        # index: Dict[str, int | IndexType | Dict[int, float]],
    ) -> None:
        return

    def generate_index(
        self: "IndexFactory",
        index: Dict[str, int | IndexType | Dict[int, float]],
    ) -> Index | None:
        timestamp: int = index.get("timestamp", IndexFactory.generate_timestamp())
        index_type: IndexType | None = index.get("type", None)
        data: Dict[int, float] | None = index.get("data", None)

        if (index_type and data):
            return Index(
                timestamp = timestamp,
                index_type = index_type,
                data = data,
            )
        else:
            return None
