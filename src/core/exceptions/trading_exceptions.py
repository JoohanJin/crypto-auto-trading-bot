"""Custom exceptions used across the trading subsystem."""

from __future__ import annotations

from src.core.exceptions.basic_exceptions import BasicException

# TODO: can implement some custom error code as well.
__all__ = [
    "TradingException",  # For Uncategorized Trading Exception
    "OrderPlacementError",
    "OrderCancellationError",
    "PositionNotFoundError",
    "InsufficientBalanceError",
    "PriceFetchError",
    "TradeConfigurationError",
]


class TradingException(BasicException):
    """Basic Exception for Trading"""


class OrderPlacementError(TradingException):
    """Raised when an order cannot be placed successfully."""


class OrderCancellationError(TradingException):
    """Raised when cancelling an existing order fails."""


class PositionNotFoundError(TradingException):
    """Raised when a requested trading position cannot be located."""


class InsufficientBalanceError(TradingException):
    """Raised when available balance is insufficient for an operation."""


class PriceFetchError(TradingException):
    """Raised when the current market price cannot be retrieved."""


class TradeConfigurationError(TradingException):
    """Raised when trade parameters or configuration are invalid."""


def _demo_traceback_trigger():
    """Helper to ensure we get a non-trivial traceback for the demo."""

    def _nested_frame():
        raise TradingException("Trading exception demo", payload = {"order_id": 42})

    _nested_frame()


if __name__ == "__main__":
    try:
        _demo_traceback_trigger()
    except TradingException as err:
        print("Payload:", err.payload)
        print("Formatted exception with traceback:\n")
        print(str(err))
