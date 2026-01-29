from __future__ import annotations

import sys
from pathlib import Path
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from core.models.constants import IndexType  # type: ignore

try:
    from data_processor import (  # type: ignore
        DataProcessor,
        IndexFactory,
    )
except ModuleNotFoundError:
    DataProcessor = None
    IndexFactory = None


class DataProcessorTest(unittest.TestCase):
    """Validate static timestamp helper without touching network resources."""

    def test_timestamp_generation_returns_int(self) -> None:
        """Ensure timestamps are emitted as integers."""
        if DataProcessor is None:
            self.skipTest("data_processor dependencies unavailable")
        timestamp = DataProcessor.generate_timestamp()
        self.assertIsInstance(timestamp, int)


class IndexFactoryTest(unittest.TestCase):
    """Cover the happy-path and failure cases for IndexFactory."""

    def test_generate_index_happy_path(self) -> None:
        """Factory should produce an Index when payload contains data."""
        if IndexFactory is None:
            self.skipTest("index factory dependencies unavailable")
        factory = IndexFactory()
        payload = {
            "timestamp": 1_700_000_000_000,
            "type": IndexType.SMA,
            "data": {5: 1.0, 10: 2.0},
        }

        index = factory.generate_index(payload)  # type: ignore[arg-type]

        self.assertIsNotNone(index)
        self.assertEqual(index.index_type, IndexType.SMA)
        self.assertEqual(index.data, payload["data"])

    def test_generate_index_returns_none_on_missing_data(self) -> None:
        """Factory should decline payloads that omit the data field."""
        if IndexFactory is None:
            self.skipTest("index factory dependencies unavailable")
        factory = IndexFactory()
        payload = {
            "timestamp": 1_700_000_000_000,
            "type": IndexType.SMA,
            "data": None,
        }

        self.assertIsNone(factory.generate_index(payload))  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
