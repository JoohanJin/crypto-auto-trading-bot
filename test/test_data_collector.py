from __future__ import annotations

import unittest

from src.data_layer.data_collector import DataCollector


class DataCollectorTest(unittest.TestCase):
    """Validate static timestamp helper without touching network resources."""

    def test_timestamp_generation_returns_int(self) -> None:
        """Ensure timestamps are emitted as integers."""
        timestamp = DataCollector.generate_timestamp()
        self.assertIsInstance(timestamp, int)


if __name__ == "__main__":
    unittest.main()
