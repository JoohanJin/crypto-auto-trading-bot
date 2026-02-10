from dataclasses import dataclass

from src.core.models.base import MutableModel
from src.core.models.trend import TrendState


@dataclass
class ScoreMetrics(MutableModel):
    timestamp: int
    current_score: float
    trend: TrendState
    velocity: float
    acceleration: float
    volatility: float
    confidence: float


class ScoreHistory:
    '''
    - Data structure to store the score history.
    - Dequeue?
    - Tree? B+ ? -> But BST is also fine I think...? hmmm
    '''
    def __init__(
        self: "ScoreHistory",
        max_size: int = 100,
    ) -> None:
        # dict[id, pointer or reference] + linked list
        # consider heap or dequeue
        return

    def add(self,) -> None:
        return

    def get_recent(self, n: int):
        return

    def get_scores_since(self, timestamp: int):
        return

    def clear(self,) -> None:
        return
