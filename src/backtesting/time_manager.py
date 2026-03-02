class MockTimeManager:
    """
    Overrides the system's time with a simulated timestamp that is updated by the DataLoader.
    This allows the entire bot to "fast-forward" through months of data in seconds,
    while still properly calculating EMA/SMA and cooldowns.
    """
    _current_time_ms: int = 0

    @classmethod
    def set_time(cls, timestamp_ms: int):
        cls._current_time_ms = timestamp_ms

    @classmethod
    def generate_timestamp(cls) -> int:
        return cls._current_time_ms

    @classmethod
    def get_time_seconds(cls) -> float:
        return cls._current_time_ms / 1000.0


def patch_system_time():
    """
    Monkey patches the `generate_timestamp` methods across the core systems
    to use the MockTimeManager instead of real time.
    """
    import time

    from src.core.models.index import Index
    from src.data.data_manager import DataManager
    from src.data.data_processor import DataProcessor
    from src.trading.trade_manager import TradeManager

    # Overwrite the generate_timestamp classmethods
    TradeManager.generate_timestamp = MockTimeManager.generate_timestamp
    DataProcessor.generate_timestamp = MockTimeManager.generate_timestamp
    DataManager.generate_timestamp = MockTimeManager.generate_timestamp
    Index.generate_timestamp = MockTimeManager.generate_timestamp

    # Overwrite python's built-in time.time() and time.sleep()
    time.time = MockTimeManager.get_time_seconds
    time.sleep = lambda secs: None  # Instantly return, no physical sleeping!

    print("[BACKTEST] Time and Sleep have been successfully mocked.")
