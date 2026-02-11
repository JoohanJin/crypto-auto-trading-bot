# STANDARD LIBRARY
from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class StrategyCondition:
    type: str
    payload: Dict[str, Any]
