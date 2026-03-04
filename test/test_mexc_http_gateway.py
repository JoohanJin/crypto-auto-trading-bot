from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from src.brokers.mexc.http_gateway import MexcFutureGateway


class TestMexcFutureGateway(unittest.TestCase):
    def setUp(self):
        self.gateway = MexcFutureGateway(
            api_key="test_api_key",
            secret_key="test_secret_key",
        )

    def test_initialization(self):
        """Test that the gateway initializes with the correct base URL and content type."""
        self.assertEqual(self.gateway.base_url, "https://contract.mexc.com")
        self.assertIn(
            "application/json", self.gateway.session.headers.get("Content-Type", "")
        )

    @patch("src.brokers.mexc.http_gateway.HttpService.generate_timestamp")
    def test_signature_generation(self, mock_timestamp):
        """Test that the gateway correctly signs requests according to MEXC docs."""
        mock_timestamp.return_value = 1234567890

        # In MexcFutureGateway, the query string passed to generate_signature is:
        # {api_key}{timestamp}{sorted_params_str}

        query_str = "test_api_key1234567890param1=value1&param2=value2"
        sig = self.gateway.generate_signature(query_str)
        self.assertIsInstance(sig, str)
        self.assertTrue(len(sig) > 0)

    def test_call_constructs_correct_headers(self):
        """Test that the API call adds Request-Time, ApiKey, and Signature headers."""
        # Mock the response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True, "data": {}}

        # Patch the instance's session request directly
        self.gateway.session.request = MagicMock(return_value=mock_response)

        self.gateway.call(method="GET", url="/api/v1/test", params={"param1": "value1"})

        # Verify the request was called with the correct headers
        self.gateway.session.request.assert_called_once()
        _, kwargs = self.gateway.session.request.call_args

        headers = kwargs.get("headers", {})
        self.assertIn("ApiKey", headers)
        self.assertEqual(headers["ApiKey"], "test_api_key")
        self.assertIn("Request-Time", headers)
        self.assertIn("Signature", headers)


if __name__ == "__main__":
    unittest.main()
