from __future__ import annotations

import sys
from pathlib import Path
import unittest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from core.models.signal import Signal, TradeSignal  # type: ignore

try:
    from trade_manager import TradeManager  # type: ignore
except ModuleNotFoundError:
    TradeManager = None


class TradeManagerUtilitiesTest(unittest.TestCase):
    """Target TradeManager helpers that do not depend on live infrastructure."""

    def test_trade_manager_timestamp(self) -> None:
        """TradeManager timestamps should be emitted as integers."""
        if TradeManager is None:
            self.skipTest("trade_manager dependencies unavailable")
        timestamp = TradeManager.generate_timestamp()
        self.assertIsInstance(timestamp, int)

    def test_verify_signal_uses_timestamp_window(self) -> None:
        """verify_signal accepts recent signals inside the configured window."""
        if TradeManager is None:
            self.skipTest("trade_manager dependencies unavailable")
        recent_signal = Signal(TradeSignal.HOLD)
        self.assertTrue(TradeManager.verify_signal(recent_signal, timestamp_window = 10_000))


if __name__ == "__main__":
    unittest.main()
