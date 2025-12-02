from __future__ import annotations

import sys
from pathlib import Path
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

try:
    from manager.data_collector import DataCollector  # type: ignore
except ModuleNotFoundError:
    DataCollector = None


class DataCollectorTest(unittest.TestCase):
    """Validate static timestamp helper without touching network resources."""

    def test_timestamp_generation_returns_int(self) -> None:
        """Ensure timestamps are emitted as integers."""
        if DataCollector is None:
            self.skipTest("data_collector dependencies unavailable")
        timestamp = DataCollector.generate_timestamp()
        self.assertIsInstance(timestamp, int)


if __name__ == "__main__":
    unittest.main()
