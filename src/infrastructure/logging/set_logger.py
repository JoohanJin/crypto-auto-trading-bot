# Standard library imports
import logging
from logging.handlers import TimedRotatingFileHandler
from functools import wraps
from pathlib import Path
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Get log directory from environment variable, default to ./log
_LOG_DIR: Path = Path(os.getenv("LOG_DIR", "./log"))
_LOG_DIR.mkdir(parents=True, exist_ok=True)

# Get log level from environment variable, default to INFO
_LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()


def setup_logger(
    name: str,
    log_filename: str,
    level: str = _LOG_LEVEL,
    add_console: bool = False
) -> logging.Logger:
    """
    Factory function to create and configure a logger with timed rotating file handler
    and optional console handler.
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, level))

    # Formatter for log messages
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(name)s - %(message)s")

    # Prevent adding handlers multiple times if the module is re-imported
    if not logger.handlers:
        # File Handler
        file_handler = TimedRotatingFileHandler(
            filename=_LOG_DIR / log_filename,
            when="midnight",
            interval=1,
            backupCount=14,
            encoding="utf-8",
            delay=False,
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # Console Handler
        if add_console:
            console_handler = logging.StreamHandler()
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

    return logger


# Initialize Loggers
operation_logger = setup_logger("OperationLogger", "system-logging.log", add_console=True)
trading_logger = setup_logger("TradingLogger", "trading-logging.log", add_console=False)


def get_logger(module_name: str, logger_type: str = "operation") -> logging.Logger:
    """
    Get a child logger for a specific module.
    
    Args:
        module_name: The name of the module (usually __name__).
        logger_type: 'operation' or 'trading'.
    """
    if logger_type.lower() == "trading":
        parent_name = "TradingLogger"
    else:
        parent_name = "OperationLogger"
        
    # Create a child logger (e.g., OperationLogger.src.main)
    # This logger will inherit handlers/level from the parent
    logger = logging.getLogger(f"{parent_name}.{module_name}")
    return logger


class ContextAdapter(logging.LoggerAdapter):
    """
    Adapter that adds a prefix to log messages.
    Usage:
        adapter = ContextAdapter(logger, {"prefix": "MyClass"})
        adapter.info("Hello") -> "OperationLogger... - [MyClass] Hello"
    """
    def process(self, msg, kwargs):
        return '[%s] %s' % (self.extra['prefix'], msg), kwargs


def get_adapter(logger: logging.Logger, prefix: str) -> logging.LoggerAdapter:
    """Helper to create a ContextAdapter."""
    return ContextAdapter(logger, {"prefix": prefix})


operation_logger.info("[SERVICE_INIT] OperationLogger initialized")
trading_logger.info("[SERVICE_INIT] TradingLogger initialized")


def log_decorator(func):
    def entering(func, *args):
        operation_logger.debug(f"Entering function '{func.__name__}'")
        operation_logger.info(
            f"Function at line {func.__code__.co_firstlineno} in {func.__code__.co_filename}"
        )

    def exiting(func):
        operation_logger.debug(f"Exiting function '{func.__name__}'")

    @wraps(func)
    def wrapper(*args, **kwargs):
        entering(func, *args)
        result = func(*args, **kwargs)
        exiting(func)
        return result

    return wrapper


if __name__ == "__main__":
    # Test the logger
    operation_logger.info("This is a test log message.")
    trading_logger.info("This is a test trading log message.")
    operation_logger.error("This is a test error log message.")
    trading_logger.error("This is a test trading error log message.")
