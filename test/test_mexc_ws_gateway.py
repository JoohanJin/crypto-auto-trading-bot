from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from src.brokers.mexc.ws_gateway import MexcWebSocket


class TestMexcWebSocketGateway(unittest.TestCase):
    def setUp(self):
        # Prevent actual thread starting during test initialization
        with patch("src.brokers.mexc.ws_gateway.MexcWebSocket.connect"):
            self.ws_gateway = MexcWebSocket(
                url="wss://contract.mexc.com/edge",
                name="TEST_MEXC_WS",
                api_key="test_api_key",
                secret_key="test_secret_key",
                ping_interval=20,
            )

    def test_initialization(self):
        """Test that internal data structures are properly initialized."""
        self.assertEqual(self.ws_gateway.url, "wss://contract.mexc.com/edge")
        self.assertEqual(self.ws_gateway.api_key, "test_api_key")
        self.assertEqual(self.ws_gateway.secret_key, "test_secret_key")
        self.assertIsInstance(self.ws_gateway.callbacks, dict)
        self.assertIsInstance(self.ws_gateway.subscriptions, list)

    def test_subscribe_adds_to_callbacks(self):
        """Test that subscribing correctly registers the callback and formats the topic."""
        mock_callback = MagicMock()

        # Mock _is_connected to bypass the connection wait loop
        with patch.object(self.ws_gateway, "_is_connected", return_value=True):
            # Mock send to avoid actual websocket I/O
            with patch.object(self.ws_gateway, "send"):
                self.ws_gateway.subscribe(
                    topic="ticker",
                    callback=mock_callback,
                    param={"symbol": "BTC_USDT"}
                )

        # MexcWebSocket prepends "sub." and registers the callback without "sub."
        self.assertIn("ticker", self.ws_gateway.callbacks)
        self.assertEqual(self.ws_gateway.callbacks["ticker"], mock_callback)

    def test_message_routing_deals_with_response(self):
        """Test that incoming WebSocket messages are properly routed to callbacks."""
        mock_callback = MagicMock()
        self.ws_gateway.callbacks["ticker"] = mock_callback

        test_msg = {
            "channel": "push.ticker",
            "data": {"price": 50000}
        }

        # Route the message
        self.ws_gateway._deal_with_response(test_msg)

        # The internal logic strips "push." and calls the callback for "ticker"
        mock_callback.assert_called_once_with(test_msg)


if __name__ == "__main__":
    unittest.main()
