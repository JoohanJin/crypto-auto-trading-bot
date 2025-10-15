import traceback
from abc import ABC


class BasicException(Exception, ABC):
    """Base exception for All the Custom Errors."""
    def __init__(
        self,
        message: str | None = None,
        *,  # after this, callers have to write TradingException()
        payload: dict | None = None,
    ) -> None:
        super().__init__(message or self.__class__.__name__)
        self.payload = payload or {}

    def __str__(self):
        base = super().__str__()
        tb = self.__traceback__
        tb = self.__traceback__
        if (tb):
            tb_summary = "".join(traceback.format_tb(tb))
            return f"{base}\nTraceback:\n{tb_summary}"
        return base
