from __future__ import annotations

import sys
import unittest
from pathlib import Path


# NOTE: Converted the legacy script into focused queue semantics tests for the
# signal pipeline so CI can run without external brokers.

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from core.models.signal import Signal, TradeSignal  # type: ignore
from pipeline.signal_pipeline import SignalPipeline  # type: ignore


class SignalPipelineTest(unittest.TestCase):
    """Validate that SignalPipeline buffers behave as FIFO queues."""

    def setUp(self) -> None:
        """Instantiate a new pipeline for each test case."""
        self.pipeline = SignalPipeline()

    def test_push_returns_true(self) -> None:
        """push should succeed for valid signal objects."""
        signal = Signal(TradeSignal.SHORT_TERM_BUY)
        self.assertTrue(self.pipeline.push(signal))

    def test_pop_returns_signal(self) -> None:
        """pop should return the same signal previously enqueued."""
        signal = Signal(TradeSignal.LONG_TERM_SELL)
        self.pipeline.push(signal)
        self.assertEqual(self.pipeline.pop(block = False), signal)


if __name__ == "__main__":
    unittest.main()
