# Standard Library
from __future__ import annotations
from dataclasses import dataclass, replace
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


@dataclass
class MutableModel:
    """
    ;Base class for all mutable data models.
    
    ;Provides a copy() method that works for all subclasses.
    """

    def copy(self: M) -> M:
        return replace(self)
