# STANDARD LIBRARY
from dataclasses import dataclass
from typing import Any


@dataclass
class StrategyCondition:
    type: str
    payload: dict[str, Any]
