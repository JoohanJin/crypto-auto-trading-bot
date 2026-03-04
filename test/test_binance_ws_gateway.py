from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from src.brokers.binance.ws_gateway import BinanceMarketWebSocket, BinanceUserWebSocket


class TestBinanceMarketWebSocket(unittest.TestCase):
    def setUp(self):
        with patch("src.brokers.binance.ws_gateway.BinanceMarketWebSocket.connect"):
            self.ws = BinanceMarketWebSocket(
                ping_interval=20,
                name="TEST_BINANCE_MARKET_WS"
            )

    def test_initialization(self):
        self.assertEqual(self.ws.url, "wss://fstream.binance.com/ws")
        self.assertIsNone(self.ws.api_key)
        self.assertIsNone(self.ws.secret_key)
        self.assertIsInstance(self.ws.callbacks, dict)

    def test_subscribe_adds_to_callbacks(self):
        mock_callback = MagicMock()

        with patch.object(self.ws, "_is_connected", return_value=True):
            with patch.object(self.ws, "send"):
                self.ws.subscribe(
                    streams="btcusdt@ticker",
                    push_topic="24hrTicker",
                    callback=mock_callback,
                )

        self.assertIn("24hrTicker", self.ws.callbacks)
        self.assertEqual(self.ws.callbacks["24hrTicker"], mock_callback)
        self.assertIn("btcusdt@ticker", self.ws.subscriptions)

    def test_message_routing_deals_with_response(self):
        mock_callback = MagicMock()
        self.ws.callbacks["24hrTicker"] = mock_callback

        test_msg = {
            "e": "24hrTicker",
            "s": "BTCUSDT",
            "c": "50000.0"
        }

        self.ws._deal_with_response(test_msg)
        mock_callback.assert_called_once_with(test_msg)


class TestBinanceUserWebSocket(unittest.TestCase):
    @patch("src.brokers.binance.ws_gateway.load_pem_private_key")
    def test_initialization(self, mock_load_key):
        with patch("src.brokers.binance.ws_gateway.BinanceUserWebSocket.connect"):
            ws = BinanceUserWebSocket(
                api_key="test_api_key",
                secret_key="fake_pem_key_string",
                ping_interval=20,
            )

        self.assertEqual(ws.url, "wss://ws-fapi.binance.com/ws-fapi/v1")
        self.assertEqual(ws.api_key, "test_api_key")
        mock_load_key.assert_called_once()

    @patch("src.brokers.binance.ws_gateway.load_pem_private_key")
    def test_construct_params_adds_signature(self, mock_load_key):
        with patch("src.brokers.binance.ws_gateway.BinanceUserWebSocket.connect"):
            ws = BinanceUserWebSocket(
                api_key="test_api_key",
                secret_key="fake_pem_key_string",
                ping_interval=20,
            )

            # Mock the signature generation since we don't have a real Ed25519 key
            ws._generate_signature = MagicMock(return_value="fake_signature")

            params = {"symbol": "BTCUSDT"}
            ws._construct_params(params)

            self.assertIn("apiKey", params)
            self.assertEqual(params["apiKey"], "test_api_key")
            self.assertIn("timestamp", params)
            self.assertIn("signature", params)
            self.assertEqual(params["signature"], "fake_signature")


if __name__ == "__main__":
    unittest.main()
