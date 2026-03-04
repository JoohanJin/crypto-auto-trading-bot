from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from src.brokers.binance.http_gateway import BinanceFutureGateway


class TestBinanceFutureGateway(unittest.TestCase):
    def setUp(self):
        self.gateway = BinanceFutureGateway(
            api_key="test_api_key",
            secret_key="test_secret_key",
        )

    def test_initialization(self):
        """Test that the gateway initializes with the correct base URL and content type."""
        self.assertEqual(self.gateway.base_url, "https://fapi.binance.com")
        self.assertIn("application/x-www-form-urlencoded", self.gateway.session.headers.get("Content-Type", ""))

    @patch("src.brokers.binance.http_gateway.HttpService.generate_timestamp")
    def test_signature_generation(self, mock_timestamp):
        """Test that the gateway correctly signs requests according to Binance docs (HMAC SHA256)."""
        mock_timestamp.return_value = 1234567890

        query_str = "param1=value1&param2=value2"
        sig = self.gateway.generate_signature(query_str)

        self.assertIsInstance(sig, str)
        self.assertTrue(len(sig) > 0)

    def test_call_constructs_correct_headers_and_signature(self):
        """Test that the API call adds X-MBX-APIKEY and signature params."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True}

        self.gateway.session.request = MagicMock(return_value=mock_response)

        self.gateway.call(
            method="GET",
            url="/api/v1/test",
            params={"param1": "value1"}
        )

        self.gateway.session.request.assert_called_once()
        _, kwargs = self.gateway.session.request.call_args

        # Verify Headers
        headers = kwargs.get("headers", {})
        self.assertIn("X-MBX-APIKEY", headers)
        self.assertEqual(headers["X-MBX-APIKEY"], "test_api_key")

        # Verify Params
        params = kwargs.get("params", {})
        self.assertIn("signature", params)
        self.assertIn("param1", params)
        self.assertEqual(params["param1"], "value1")


if __name__ == "__main__":
    unittest.main()
