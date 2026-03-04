"""
Automated Test Suite for WebSocketInterface
============================================
Tests the WebSocketInterface with real Mexc and Binance WebSocket clients.

Verifies:
- Interface initialization and configuration
- Client registration (push/get/pop)
- WebSocket connections start successfully
- Ticker subscription delivers Ticker DTOs from both brokers
- Data arrives from multiple sources concurrently
- Type safety (rejects non-WebSocketClient)
- Graceful handling of errors
"""

import os
import sys
import threading
import time
import unittest

import pytest


sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.brokers.binance.ws_client import BinanceWebSocketClient
from src.brokers.mexc.ws_client import MexcWebSocketClient
from src.core.models.service_dto import Ticker
from src.core.models.trade import TradePair
from src.interfaces.websocket_interface import WebSocketInterface
from src.interfaces.ws_client_registry import WebSocketClientRegistry


# ──────────────────────────────────────────────
# Shared State for Callback Collection
# ──────────────────────────────────────────────

class TickerCollector:
    """Thread-safe collector for Ticker callbacks."""
    def __init__(self):
        self._lock = threading.Lock()
        self._tickers: list[Ticker] = []

    def callback(self, ticker: Ticker) -> None:
        with self._lock:
            self._tickers.append(ticker)

    @property
    def tickers(self) -> list[Ticker]:
        with self._lock:
            return list(self._tickers)

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._tickers)

    @property
    def sources(self) -> set[str]:
        with self._lock:
            return {t.source for t in self._tickers}


# ──────────────────────────────────────────────
# Unit Tests: Interface Setup (no network)
# ──────────────────────────────────────────────

class TestWebSocketInterfaceSetup(unittest.TestCase):
    """Unit tests for WebSocketInterface construction and registry operations."""

    def test_01_default_initialization(self):
        """Interface initializes with default TradePair and registry."""
        wsi = WebSocketInterface()
        self.assertEqual(wsi.trade_pair, TradePair("BTC", "USDT"))
        self.assertIsNotNone(wsi.client_registry)

    def test_02_custom_trade_pair(self):
        """Interface accepts a custom TradePair."""
        tp = TradePair("ETH", "USDT")
        wsi = WebSocketInterface(trade_pair=tp)
        self.assertEqual(wsi.trade_pair.ticker, "ETH")
        self.assertEqual(wsi.trade_pair.quote, "USDT")

    def test_03_custom_registry(self):
        """Interface accepts an injected registry."""
        registry = WebSocketClientRegistry(name="CUSTOM")
        wsi = WebSocketInterface(client_registry=registry)
        self.assertIs(wsi.client_registry, registry)

    def test_04_push_and_get_client(self):
        """push_client registers a client retrievable by get_client."""
        wsi = WebSocketInterface()
        mexc = MexcWebSocketClient(name="TEST_MEXC")
        wsi.push_client("mexc", mexc)
        self.assertIs(wsi.get_client("mexc"), mexc)

    def test_05_push_multiple_clients(self):
        """Multiple clients can be registered under different keys."""
        wsi = WebSocketInterface()
        mexc = MexcWebSocketClient(name="TEST_MEXC")
        binance = BinanceWebSocketClient(name="TEST_BINANCE")
        wsi.push_client("mexc", mexc)
        wsi.push_client("binance", binance)
        self.assertIs(wsi.get_client("mexc"), mexc)
        self.assertIs(wsi.get_client("binance"), binance)

    def test_06_pop_client(self):
        """pop_client removes a registered client."""
        wsi = WebSocketInterface()
        mexc = MexcWebSocketClient(name="TEST_MEXC")
        wsi.push_client("mexc", mexc)
        wsi.pop_client("mexc")
        self.assertIsNone(wsi.get_client("mexc"))

    def test_07_get_nonexistent_client(self):
        """get_client returns None for unregistered key."""
        wsi = WebSocketInterface()
        self.assertIsNone(wsi.get_client("nonexistent"))

    def test_08_push_rejects_non_websocket_client(self):
        """push_client raises TypeError for non-WebSocketClient."""
        wsi = WebSocketInterface()
        with self.assertRaises(TypeError):
            wsi.push_client("bad", "not_a_client")  # type: ignore

    def test_09_push_overwrites_existing_key(self):
        """Pushing a new client with an existing key overwrites it."""
        wsi = WebSocketInterface()
        mexc1 = MexcWebSocketClient(name="MEXC_1")
        mexc2 = MexcWebSocketClient(name="MEXC_2")
        wsi.push_client("mexc", mexc1)
        wsi.push_client("mexc", mexc2)
        self.assertIs(wsi.get_client("mexc"), mexc2)

    def test_10_registry_reflects_all_clients(self):
        """Registry property contains all pushed clients."""
        wsi = WebSocketInterface()
        mexc = MexcWebSocketClient(name="TEST_MEXC")
        binance = BinanceWebSocketClient(name="TEST_BINANCE")
        wsi.push_client("mexc", mexc)
        wsi.push_client("binance", binance)
        registry = wsi.client_registry.registry
        self.assertEqual(len(registry), 2)
        self.assertIn("mexc", registry)
        self.assertIn("binance", registry)


# ──────────────────────────────────────────────
# Integration Tests: Live WebSocket (network)
# ──────────────────────────────────────────────

@pytest.mark.slow
@pytest.mark.integration
class TestWebSocketInterfaceLive(unittest.TestCase):
    """
    Integration tests with real Mexc and Binance WebSocket connections.
    Requires network access. Ticker data is public (no API keys needed).
    """

    @classmethod
    def setUpClass(cls):
        """Build interface with both brokers and subscribe to ticker."""
        cls.trade_pair = TradePair("BTC", "USDT")
        cls.collector = TickerCollector()

        cls.mexc_client = MexcWebSocketClient(name="LIVE_MEXC")
        cls.binance_client = BinanceWebSocketClient(name="LIVE_BINANCE")

        cls.registry = WebSocketClientRegistry(name="LIVE_REGISTRY")
        cls.wsi = WebSocketInterface(
            client_registry=cls.registry,
            trade_pair=cls.trade_pair,
        )

        cls.wsi.push_client("mexc", cls.mexc_client)
        cls.wsi.push_client("binance", cls.binance_client)

        # Start connections
        cls.wsi.start()

        # Subscribe to ticker
        cls.wsi.ticker(callback=cls.collector.callback)

        # Wait for data to arrive
        print("\n[SETUP] Waiting 12s for ticker data from Mexc & Binance...")
        time.sleep(12)

    # ── Connection Tests ──

    def test_11_received_ticker_data(self):
        """Should receive at least one Ticker after subscribing."""
        self.assertGreater(
            self.collector.count, 0,
            "Should have received at least one Ticker"
        )

    def test_12_all_tickers_are_dto(self):
        """Every received item should be a Ticker dataclass."""
        for t in self.collector.tickers:
            self.assertIsInstance(t, Ticker, f"Expected Ticker, got {type(t)}")

    def test_13_ticker_has_positive_price(self):
        """Each Ticker should have a positive price."""
        for t in self.collector.tickers:
            self.assertGreater(t.price, 0, f"Price should be positive, got {t.price}")

    def test_14_ticker_has_timestamp(self):
        """Each Ticker should have a recent positive timestamp."""
        for t in self.collector.tickers:
            self.assertGreater(t.timestamp, 0, "Timestamp should be positive")

    def test_15_ticker_has_source(self):
        """Each Ticker should have a non-empty source string."""
        for t in self.collector.tickers:
            self.assertIsInstance(t.source, str)
            self.assertTrue(len(t.source) > 0, "Source should not be empty")

    def test_16_ticker_has_trade_pair(self):
        """Each Ticker should carry a TradePair."""
        for t in self.collector.tickers:
            self.assertIsInstance(t.ticker, TradePair)

    def test_17_ticker_trade_pair_is_btc_usdt(self):
        """TradePair should be BTC/USDT (what we subscribed to)."""
        for t in self.collector.tickers:
            self.assertEqual(t.ticker.ticker.upper(), "BTC", f"Expected BTC, got {t.ticker.ticker}")
            self.assertEqual(t.ticker.quote.upper(), "USDT", f"Expected USDT, got {t.ticker.quote}")

    # ── Multi-Source Tests ──

    def test_18_receives_from_mexc(self):
        """Should receive tickers sourced from MEXC."""
        sources = self.collector.sources
        self.assertIn(
            "MEXC", {s.upper() for s in sources},
            f"Expected MEXC in sources, got {sources}"
        )

    def test_19_receives_from_binance(self):
        """Should receive tickers sourced from Binance."""
        sources = self.collector.sources
        self.assertIn(
            "BINANCE", {s.upper() for s in sources},
            f"Expected BINANCE in sources, got {sources}"
        )

    def test_20_both_sources_present(self):
        """Should receive data from both sources concurrently."""
        sources = {s.upper() for s in self.collector.sources}
        self.assertTrue(
            {"MEXC", "BINANCE"}.issubset(sources),
            f"Expected both MEXC and BINANCE, got {sources}"
        )

    # ── Data Quality Tests ──

    def test_21_price_in_reasonable_range(self):
        """BTC price should be in a reasonable range (sanity check)."""
        for t in self.collector.tickers:
            self.assertGreater(t.price, 1_000, f"BTC price too low: {t.price}")
            self.assertLess(t.price, 500_000, f"BTC price too high: {t.price}")

    def test_22_continuous_data_flow(self):
        """More data should arrive over time."""
        count_before = self.collector.count
        time.sleep(3)
        count_after = self.collector.count
        self.assertGreater(
            count_after, count_before,
            "Ticker count should increase over time"
        )

    def test_23_multiple_tickers_received(self):
        """Should receive many tickers over 12+ seconds (at least 5)."""
        self.assertGreater(
            self.collector.count, 5,
            f"Expected at least 5 tickers, got {self.collector.count}"
        )

    # ── Thread Safety Tests ──

    def test_24_concurrent_callback_access(self):
        """Multiple threads reading the collected tickers should not crash."""
        errors = []

        def reader():
            for _ in range(50):
                try:
                    _ = self.collector.count
                    _ = self.collector.sources
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
