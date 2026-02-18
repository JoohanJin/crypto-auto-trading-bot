# Standard Library
from __future__ import annotations
from dataclasses import dataclass, replace
import time
from typing import TypeVar
from enum import IntFlag

T = TypeVar('T', bound='ImmutableModel')
M = TypeVar('M', bound='MutableModel')


class Side(IntFlag):
    BUY = 1 << 0  # 0001
    SELL = 1 << 1  # 0010


@dataclass(frozen=True)
class TradePair:
    '''
    - Custom Data Structure with ticker and quote
        - Ticker: BTC by default
        - Quote: USDT by default (USDC in the future)
    '''
    ticker: str
    quote: str


@dataclass(frozen=True)
class ImmutableModel:
    """
    ;Base class for all immutable data models.
    
    ;Provides a copy() method that works for all subclasses.
    """

    def copy(self: T) -> T:
        return replace(self)
    
    @classmethod
    def generate_timestamp(cls) -> int:
        return int(time.time() * 1_000)


@dataclass
class MutableModel:
    """
    ;Base class for all mutable data models.
    
    ;Provides a copy() method that works for all subclasses.
    """

    def copy(self: M) -> M:
        return replace(self)
    
    @classmethod
    def generate_timestamp(cls) -> int:
        return int(time.time() * 1_000)
