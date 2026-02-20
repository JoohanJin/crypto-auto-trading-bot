from __future__ import annotations

import unittest

from src.data.data_collector import DataCollector


class DataCollectorTest(unittest.TestCase):
    """Validate static timestamp helper without touching network resources."""

    def setUp(self) -> None:
        try:
            self.data_collector: DataCollector = DataCollector()
        except Exception as e:
            print(f"{str(e)}")
        return

    def test_timestamp_generation_returns_int(self) -> None:
        """Ensure timestamps are emitted as integers."""
        if not isinstance(self.data_collector, DataCollector):
            self.skipTest("data_collector dependencies unavailable")
        timestamp = DataCollector.generate_timestamp()
        self.assertIsInstance(timestamp, int)


if __name__ == "__main__":
    unittest.main()
