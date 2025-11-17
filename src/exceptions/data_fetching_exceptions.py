import traceback

from src.exceptions.basic_exceptions import BasicException

__all__ = ["DataFetchingException"]


class DataFetchingException(BasicException):
    """Basic Exception for Data Fetching"""
