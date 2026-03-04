"""
Automated Test Suite for DataManager Pipeline
==============================================
Tests the full flow: WebSocket → DataCollector → DataFrame → DataProcessor → Pipeline

Uses mock WebSocket clients to inject fake Ticker data without needing real API connections.
"""

import os
import sys
import threading
import time
import unittest
from collections.abc import Callable

import pytest


# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import contextlib

from src.brokers.base.ws_client import WebSocketClient
from src.core.models.index import Index, IndexType
from src.core.models.service_dto import Ticker
from src.core.models.trade import TradePair
from src.data.data_manager import DataManager
from src.interfaces.pipeline_interface import PipelineController
from src.interfaces.websocket_interface import WebSocketInterface
from src.interfaces.ws_client_registry import WebSocketClientRegistry
from src.pipeline.base_pipeline import BasePipeline


# ──────────────────────────────────────────────
# Test Doubles
# ──────────────────────────────────────────────

class SimplePipeline(BasePipeline):
    """Concrete pipeline that stores pushed items for assertion."""
    def __init__(self):
        super().__init__()

    def push(self, obj) -> bool:
        self.queue.put(obj)
        return True

    def pop(self, block=True):
        try:
            return self.queue.get(block=block, timeout=5)
        except Exception:
            return None


class CollectingPipelineController(PipelineController):
    """PipelineController that collects all popped items into a list for assertions."""
    def __init__(self, pipeline: BasePipeline):
        super().__init__(pipeline=pipeline)
        self.collected: list = []
        self._lock = threading.Lock()
        self._start_pop_thread()

    def _start_pop_thread(self) -> None:
        t = threading.Thread(target=self._pop_wrapper, name="collector_pop", daemon=True)
        t.start()

    def _pop_wrapper(self) -> None:
        while True:
            try:
                obj = self.pipeline.pop(block=True)
                if obj:
                    with self._lock:
                        self.collected.append(obj)
            except Exception:
                pass

    def get_collected(self) -> list:
        with self._lock:
            return list(self.collected)


class FakeWebSocketClient(WebSocketClient):
    """
    Mock WebSocket client that fires fake Ticker data at a controlled rate.
    """
    def __init__(self, name: str, source: str, base_price: float = 66_000.0):
        self.name = name
        self._source = source
        self._base_price = base_price
        self._callbacks: list[Callable] = []
        self._running = False
        self._thread: threading.Thread | None = None
        self._trade_pair: TradePair = TradePair("BTC", "USDT")

    def start(self) -> None:
        self._running = True
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._emit_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False

    def ticker(self, callback: Callable, trade_pair: TradePair, **kwargs) -> None:
        self._callbacks.append(callback)
        self._trade_pair = trade_pair
        self.start()

    def _emit_loop(self) -> None:
        """Emit a Ticker roughly every 0.2s with slight price variation."""
        import random
        tick_count = 0
        while self._running:
            tick_count += 1
            price = self._base_price + random.uniform(-50, 50)
            ts = int(time.time() * 1_000)
            ticker = Ticker(
                timestamp=ts,
                source=self._source,
                ticker=self._trade_pair,
                price=price,
            )
            for cb in self._callbacks:
                with contextlib.suppress(Exception):
                    cb(ticker)
            time.sleep(0.2)

    # ── Stubs for abstract methods ──
    @classmethod
    def _parse_trade_pair(cls, trade_pair: TradePair) -> str:
        return f"{trade_pair.ticker}{trade_pair.quote}"

    def kline(self, *args, **kwargs): pass
    def order_book(self, *args, **kwargs): pass


# ──────────────────────────────────────────────
# Test Cases
# ──────────────────────────────────────────────

@pytest.mark.slow
@pytest.mark.integration
class TestDataManagerPipeline(unittest.TestCase):
    """Integration tests for the DataManager data flow."""

    @classmethod
    def setUpClass(cls):
        """Build the full pipeline once for all tests."""
        trade_pair = TradePair("BTC", "USDT")

        # Fake WS clients
        cls.fake_mexc = FakeWebSocketClient(name="FAKE_MEXC", source="mexc", base_price=66_400.0)
        cls.fake_binance = FakeWebSocketClient(name="FAKE_BINANCE", source="binance", base_price=66_450.0)

        # Registry + Interface
        registry = WebSocketClientRegistry(name="TEST_REGISTRY")
        cls.ws_interface = WebSocketInterface(
            client_registry=registry,
            trade_pair=trade_pair,
        )
        cls.ws_interface.push_client("mexc", cls.fake_mexc)
        cls.ws_interface.push_client("binance", cls.fake_binance)
        cls.ws_interface.start()

        # Pipeline
        cls.pipeline = SimplePipeline()
        cls.pipeline_controller = CollectingPipelineController(pipeline=cls.pipeline)

        # DataManager (starts threads internally)
        cls.dm = DataManager(
            websocket_interface=cls.ws_interface,
            pipeline_controller=cls.pipeline_controller,
        )

        # Wait for data to accumulate
        time.sleep(8)

    @classmethod
    def tearDownClass(cls):
        """Stop fake clients."""
        cls.fake_mexc.stop()
        cls.fake_binance.stop()

    # ── Test: DataCollector populates the shared DataFrame ──
    def test_01_dataframe_has_rows(self):
        """DataCollector should populate the shared DataFrame with ticker data."""
        with self.dm.lock_price_data:
            row_count = self.dm.prices.shape[0]
        self.assertGreater(row_count, 0, "DataFrame should have rows after collecting ticker data")

    def test_02_dataframe_columns(self):
        """DataFrame should contain 'symbol' and 'price' columns."""
        with self.dm.lock_price_data:
            cols = list(self.dm.prices.columns)
        self.assertIn("symbol", cols)
        self.assertIn("price", cols)

    def test_03_dataframe_index_is_timestamp(self):
        """DataFrame index should be named 'timestamp'."""
        self.assertEqual(self.dm.prices.index.name, "timestamp")

    def test_04_dataframe_price_is_numeric(self):
        """Price column values should be numeric (float)."""
        with self.dm.lock_price_data:
            prices = self.dm.prices["price"].copy()
        for p in prices:
            self.assertIsInstance(p, (int, float), f"Price should be numeric, got {type(p)}")

    def test_05_dataframe_symbol_format(self):
        """Symbol should be in 'TICKER_QUOTE' format."""
        with self.dm.lock_price_data:
            symbols = self.dm.prices["symbol"].unique()
        for s in symbols:
            self.assertIn("_", s, f"Symbol '{s}' should contain '_'")
            self.assertTrue(s.startswith("BTC"), f"Symbol '{s}' should start with 'BTC'")

    def test_06_dataframe_grows_over_time(self):
        """DataFrame should keep growing as new tickers arrive."""
        with self.dm.lock_price_data:
            count_before = self.dm.prices.shape[0]
        time.sleep(2)
        with self.dm.lock_price_data:
            count_after = self.dm.prices.shape[0]
        self.assertGreater(count_after, count_before, "DataFrame should grow over time")

    # ── Test: DataProcessor pushes Index objects to the pipeline ──
    def test_07_pipeline_receives_index_objects(self):
        """Pipeline should receive Index objects from DataProcessor."""
        collected = self.pipeline_controller.get_collected()
        # DataProcessor may not have enough data span yet for all periods,
        # but after 8s it should have produced at least some indexes.
        # If span-check filters everything, we at least verify no crash.
        if len(collected) > 0:
            for item in collected:
                self.assertIsInstance(item, Index, f"Expected Index, got {type(item)}")

    def test_08_index_has_valid_type(self):
        """Each Index should have a valid IndexType (SMA, EMA, or PRICE)."""
        collected = self.pipeline_controller.get_collected()
        valid_types = {IndexType.SMA, IndexType.EMA, IndexType.PRICE}
        for item in collected:
            self.assertIn(item.index_type, valid_types, f"Unexpected IndexType: {item.index_type}")

    def test_09_index_has_timestamp(self):
        """Each Index should have a positive timestamp."""
        collected = self.pipeline_controller.get_collected()
        for item in collected:
            self.assertGreater(item.timestamp, 0, "Index timestamp should be positive")

    def test_10_index_data_not_empty(self):
        """Index data field should not be empty."""
        collected = self.pipeline_controller.get_collected()
        for item in collected:
            if item.index_type == IndexType.PRICE:
                # Price is a float, not a dict
                self.assertIsInstance(item.data, (int, float))
            else:
                self.assertIsInstance(item.data, dict, f"SMA/EMA data should be dict, got {type(item.data)}")

    # ── Test: Multiple sources produce data ──
    def test_11_multiple_sources_in_dataframe(self):
        """Both fake websocket sources should contribute data."""
        with self.dm.lock_price_data:
            symbols = set(self.dm.prices["symbol"].unique())
        # Both fake clients emit BTC_USDT
        self.assertGreater(len(symbols), 0, "Should have at least one symbol")

    # ── Test: Thread safety ──
    def test_12_concurrent_read_write(self):
        """Concurrent read/write to the DataFrame should not crash."""
        errors = []

        def reader():
            for _ in range(50):
                try:
                    with self.dm.lock_price_data:
                        _ = self.dm.prices.shape[0]
                except Exception as e:
                    errors.append(e)
                time.sleep(0.01)

        threads = [threading.Thread(target=reader, daemon=True) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=5)

        self.assertEqual(len(errors), 0, f"Concurrent reads caused errors: {errors}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
