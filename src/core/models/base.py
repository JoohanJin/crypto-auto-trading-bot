# Standard Library
from __future__ import annotations

import time
from dataclasses import dataclass, replace
from enum import IntFlag
from typing import TypeVar


T = TypeVar('T', bound='ImmutableModel')
M = TypeVar('M', bound='MutableModel')


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


class Side(IntFlag):
    BUY = 1 << 0  # 0001
    SELL = 1 << 1  # 0010


@dataclass(frozen=True)
class TradePair(ImmutableModel):
    '''
    - Custom Data Structure with ticker and quote
        - Ticker: BTC by default
        - Quote: USDT by default (USDC in the future)
    '''
    ticker: str
    quote: str
