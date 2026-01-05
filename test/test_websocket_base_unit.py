from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

try:
    from service.mexc.websocket_base import _FutureWebSocketManager  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - optional dependency chain
    _FutureWebSocketManager = None  # type: ignore[misc]


class FutureWebSocketManagerRoutingTest(unittest.TestCase):
    def setUp(self) -> None:
        if _FutureWebSocketManager is None:
            self.skipTest("websocket base dependencies unavailable")
        # Bypass __init__ to avoid network connections.
        self.manager = _FutureWebSocketManager.__new__(_FutureWebSocketManager)

    def test_auth_message_routed(self) -> None:
        handler = mock.Mock()
        self.manager._deal_with_auth_msg = handler  # type: ignore[attr-defined]
        self.manager._deal_with_sub_msg = mock.Mock()  # type: ignore[attr-defined]
        self.manager._deal_with_normal_msg = mock.Mock()  # type: ignore[attr-defined]

        self.manager._deal_with_response({"channel": "rs.login", "data": "success"})

        handler.assert_called_once()

    def test_subscription_message_routed(self) -> None:
        handler = mock.Mock()
        self.manager._deal_with_auth_msg = mock.Mock()  # type: ignore[attr-defined]
        self.manager._deal_with_sub_msg = handler  # type: ignore[attr-defined]
        self.manager._deal_with_normal_msg = mock.Mock()  # type: ignore[attr-defined]

        self.manager._deal_with_response({"channel": "rs.sub.ticker", "data": "ok"})

        handler.assert_called_once()

    def test_normal_message_routed(self) -> None:
        handler = mock.Mock()
        self.manager._deal_with_auth_msg = mock.Mock()  # type: ignore[attr-defined]
        self.manager._deal_with_sub_msg = mock.Mock()  # type: ignore[attr-defined]
        self.manager._deal_with_normal_msg = handler  # type: ignore[attr-defined]
        self.manager._get_callback = mock.Mock(return_value=None)  # type: ignore[attr-defined]

        self.manager._deal_with_response({"channel": "push.ticker", "data": {"foo": "bar"}})

        handler.assert_called_once()


if __name__ == "__main__":
    unittest.main()
