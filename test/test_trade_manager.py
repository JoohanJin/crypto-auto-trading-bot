"""
TradeManager Unit Tests
=======================
Tests for the core trading logic in TradeManager.
Mocks external dependencies (Binance API, Telegram, pipelines) to test logic in isolation.
"""
import unittest
import time
from unittest.mock import MagicMock, patch

# Core Models
from src.core.models.trade import TradePair, TradeState, PositionState
from src.core.models.order import Order, Side
from src.core.models.signal import Signal, TradeSignal
from src.core.models.score_mapping import ScoreMapper
from src.core.models.service_dto import MarkPrice, AccountInformation

# System Under Test
from src.trading.trade_manager import TradeManager


def _make_trade_manager(**overrides) -> TradeManager:
    """
    Factory helper: creates a TradeManager with all deps mocked and start() patched out.
    """
    defaults = dict(
        signal_pipeline_controller=MagicMock(),
        http_interface=MagicMock(),
        binance_future_client=MagicMock(),
        delta_mapper=ScoreMapper(),
        telegram_bot=MagicMock(),
        trade_pair=TradePair(ticker="BTC", quote="USDT"),
        leverage=10,
        trade_weight=0.1,
        take_profit_rate=0.2,
        stop_loss_rate=0.2,
        score_threashold=50,
        score_trend_management=0,
        name="TEST",
    )
    defaults.update(overrides)
    with patch.object(TradeManager, "start", return_value=None):
        return TradeManager(**defaults)


def _make_order(side: Side = Side.BUY, **overrides) -> Order:
    """
    Factory helper: creates a minimal Order for testing.
    """
    defaults = dict(
        side=side,
        side_str="BUY" if side == Side.BUY else "SELL",
        leverage=10,
        entry_price=100_000.0,
        tp_price=102_000.0,
        sl_price=98_000.0,
        trade_pair=TradePair(ticker="BTC", quote="USDT"),
        ticker="BTC",
        ticker_size=0.01,
        quote="USDT",
        quote_size=100.0,
        meta_data={},
    )
    defaults.update(overrides)
    return Order(**defaults)


def _make_position(side: Side = Side.BUY, **overrides) -> PositionState:
    """
    Factory helper: creates a minimal PositionState for testing.
    """
    defaults = dict(
        side=side,
        ticker_size=0.01,
        quote_size=100.0,
        entry_price=100_000.0,
        timestamp=int(time.time() * 1_000),
    )
    defaults.update(overrides)
    return PositionState(**defaults)


# =============================================================================
# 1. _decide_trade() Tests
# =============================================================================
class TestDecideTrade(unittest.TestCase):
    """Test the _decide_trade() state machine."""

    def setUp(self):
        self.tm = _make_trade_manager(score_threashold=2_000)

    # --- No position held (current_order is None) ---

    def test_no_position_score_above_threshold_returns_new_buy(self):
        """score > threshold → NEW_BUY"""
        result = self.tm._decide_trade(score=2_001)
        self.assertEqual(result, TradeState.NEW_BUY)

    def test_no_position_score_at_threshold_returns_hold(self):
        """score == threshold → HOLD (not strictly greater)"""
        result = self.tm._decide_trade(score=2_000)
        self.assertEqual(result, TradeState.HOLD)

    def test_no_position_score_below_neg_threshold_returns_new_sell(self):
        """score < -threshold → NEW_SELL"""
        result = self.tm._decide_trade(score=-2_001)
        self.assertEqual(result, TradeState.NEW_SELL)

    def test_no_position_score_at_neg_threshold_returns_hold(self):
        """score == -threshold → HOLD (not strictly less)"""
        result = self.tm._decide_trade(score=-2_000)
        self.assertEqual(result, TradeState.HOLD)

    def test_no_position_score_in_range_returns_hold(self):
        """score between -threshold and threshold → HOLD"""
        result = self.tm._decide_trade(score=500)
        self.assertEqual(result, TradeState.HOLD)

    def test_no_position_score_zero_returns_hold(self):
        result = self.tm._decide_trade(score=0)
        self.assertEqual(result, TradeState.HOLD)

    # --- Position held (current_position is set) ---

    def test_sell_position_high_score_returns_reverse_buy(self):
        """
        Holding SELL position + score > threshold//2 → REVERSE_BUY.
        """
        pos = _make_position(side=Side.SELL)
        with self.tm.lock_current_position:
            self.tm.current_position = pos
        result = self.tm._decide_trade(score=1_001)
        self.assertEqual(result, TradeState.REVERSE_BUY)

    def test_buy_position_low_score_returns_reverse_sell(self):
        """
        Holding BUY position + score < -threshold//2 → REVERSE_SELL.
        """
        pos = _make_position(side=Side.BUY)
        with self.tm.lock_current_position:
            self.tm.current_position = pos
        result = self.tm._decide_trade(score=-1_001)
        self.assertEqual(result, TradeState.REVERSE_SELL)

    def test_position_held_score_in_deadzone_returns_hold(self):
        """Score within exit_threshold (threshold//4) → HOLD regardless of position."""
        pos = _make_position(side=Side.BUY)
        with self.tm.lock_current_position:
            self.tm.current_position = pos
        # exit_threshold = 2000 // 4 = 500, score=-499 is within deadzone
        result = self.tm._decide_trade(score=-499)
        self.assertEqual(result, TradeState.HOLD)

    # --- EXIT tests ---

    def test_buy_position_moderate_negative_score_returns_exit(self):
        """
        LONG position + score below -exit_threshold but above -reverse_threshold → EXIT.
        exit_threshold = 2000 // 4 = 500, reverse_threshold = 2000 // 2 = 1000
        """
        pos = _make_position(side=Side.BUY)
        with self.tm.lock_current_position:
            self.tm.current_position = pos
        result = self.tm._decide_trade(score=-501)
        self.assertEqual(result, TradeState.EXIT)

    def test_sell_position_moderate_positive_score_returns_exit(self):
        """
        SHORT position + score above exit_threshold but below reverse_threshold → EXIT.
        """
        pos = _make_position(side=Side.SELL)
        with self.tm.lock_current_position:
            self.tm.current_position = pos
        result = self.tm._decide_trade(score=501)
        self.assertEqual(result, TradeState.EXIT)

    def test_buy_position_at_exit_threshold_returns_hold(self):
        """score == -exit_threshold (exact boundary) → HOLD (strict inequality)."""
        pos = _make_position(side=Side.BUY)
        with self.tm.lock_current_position:
            self.tm.current_position = pos
        result = self.tm._decide_trade(score=-500)  # -exit_threshold exactly
        self.assertEqual(result, TradeState.HOLD)

    def test_exit_does_not_trigger_without_position(self):
        """No position → score in exit range does nothing (needs NEW threshold)."""
        self.tm.current_position = None
        result = self.tm._decide_trade(score=-501)
        self.assertEqual(result, TradeState.HOLD)

    def test_reverse_takes_priority_over_exit(self):
        """
        Score crosses both exit and reverse thresholds → REVERSE wins
        (REVERSE is checked first in the code).
        """
        pos = _make_position(side=Side.BUY)
        with self.tm.lock_current_position:
            self.tm.current_position = pos
        result = self.tm._decide_trade(score=-1_001)
        self.assertEqual(result, TradeState.REVERSE_SELL)  # not EXIT


# =============================================================================
# 2. _get_target_prices() Tests
# =============================================================================
class TestGetTargetPrices(unittest.TestCase):
    """Test TP/SL price calculations."""

    def setUp(self):
        self.tm = _make_trade_manager(
            take_profit_rate=0.2,
            stop_loss_rate=0.2,
            leverage=10,
        )

    def test_long_tp_above_sl_below(self):
        """Long position: TP above entry, SL below entry."""
        tp, sl = self.tm._get_target_prices(
            buy_or_sell=TradeState.NEW_BUY,
            current_price=100_000.0,
        )
        # tp = 100000 * (1 + 0.2/10) = 100000 * 1.02 = 102000
        # sl = 100000 * (1 - 0.2/10) = 100000 * 0.98 = 98000
        self.assertEqual(tp, 102_000.0)
        self.assertEqual(sl, 98_000.0)

    def test_short_tp_below_sl_above(self):
        """Short position: TP below entry, SL above entry."""
        tp, sl = self.tm._get_target_prices(
            buy_or_sell=TradeState.NEW_SELL,
            current_price=100_000.0,
        )
        # tp = 100000 * (1 - 0.2/10) = 98000
        # sl = 100000 * (1 + 0.2/10) = 102000
        self.assertEqual(tp, 98_000.0)
        self.assertEqual(sl, 102_000.0)

    def test_reverse_buy_uses_long_formula(self):
        """REVERSE_BUY (8) uses long formula (same as NEW_BUY)."""
        tp, sl = self.tm._get_target_prices(
            buy_or_sell=TradeState.REVERSE_BUY,
            current_price=50_000.0,
        )
        expected_tp = round(50_000 * (1 + 0.2 / 10), 2)
        expected_sl = round(50_000 * (1 - 0.2 / 10), 2)
        self.assertEqual(tp, expected_tp)
        self.assertEqual(sl, expected_sl)

    def test_reverse_sell_uses_short_formula(self):
        """REVERSE_SELL (16) uses short formula (same as NEW_SELL)."""
        tp, sl = self.tm._get_target_prices(
            buy_or_sell=TradeState.REVERSE_SELL,
            current_price=50_000.0,
        )
        expected_tp = round(50_000 * (1 - 0.2 / 10), 2)
        expected_sl = round(50_000 * (1 + 0.2 / 10), 2)
        self.assertEqual(tp, expected_tp)
        self.assertEqual(sl, expected_sl)


# =============================================================================
# 3. verify_signal() Tests
# =============================================================================
class TestVerifySignal(unittest.TestCase):
    """Test signal timestamp validation."""

    def setUp(self):
        self.tm = _make_trade_manager()

    def test_fresh_signal_is_valid(self):
        """Signal created just now should pass validation."""
        signal = Signal(signal=TradeSignal.SHORT_TERM_BUY)
        self.assertTrue(self.tm.verify_signal(signal))

    def test_stale_signal_is_invalid(self):
        """Signal older than window should fail validation."""
        signal = Signal(signal=TradeSignal.SHORT_TERM_BUY)
        # Manually backdating the internals
        signal._timestamp = int(time.time() * 1_000) - 10_000  # 10s ago
        self.assertFalse(self.tm.verify_signal(signal, timestamp_window=5_000))

    def test_custom_window(self):
        """Custom timestamp window is respected."""
        signal = Signal(signal=TradeSignal.SHORT_TERM_BUY)
        signal._timestamp = int(time.time() * 1_000) - 3_000  # 3s ago
        self.assertTrue(self.tm.verify_signal(signal, timestamp_window=5_000))
        self.assertFalse(self.tm.verify_signal(signal, timestamp_window=2_000))


# =============================================================================
# 4. _calculate_signal_score_delta() Tests
# =============================================================================
class TestCalculateSignalScoreDelta(unittest.TestCase):
    """Test score delta mapping from TradeSignal."""

    def setUp(self):
        self.tm = _make_trade_manager()

    def test_short_term_buy_delta(self):
        self.assertEqual(self.tm._calculate_signal_score_delta(TradeSignal.SHORT_TERM_BUY), 2)

    def test_long_term_buy_delta(self):
        self.assertEqual(self.tm._calculate_signal_score_delta(TradeSignal.LONG_TERM_BUY), 5)

    def test_short_term_sell_delta(self):
        self.assertEqual(self.tm._calculate_signal_score_delta(TradeSignal.SHORT_TERM_SELL), -2)

    def test_long_term_sell_delta(self):
        self.assertEqual(self.tm._calculate_signal_score_delta(TradeSignal.LONG_TERM_SELL), -5)

    def test_hold_delta_is_zero(self):
        self.assertEqual(self.tm._calculate_signal_score_delta(TradeSignal.HOLD), 0)


# =============================================================================
# 5. _construct_new_order() Tests
# =============================================================================
class TestConstructNewOrder(unittest.TestCase):
    """Test order object construction for NEW and REVERSE trades."""

    def setUp(self):
        self.tm = _make_trade_manager()
        # Mock network calls
        self.tm._get_mark_price = MagicMock(return_value=MarkPrice(
            timestamp=int(time.time() * 1000),
            source="test",
            ticker=TradePair(ticker="BTC", quote="USDT"),
            mark_price=100_000.0,
        ))
        self.tm._get_trade_quote_amt = MagicMock(return_value=100.0)
        self.tm._get_trade_ticker_amt = MagicMock(return_value=0.01)

    def test_new_buy_order_fields(self):
        """NEW_BUY → side=BUY, correct prices, no reverse in meta_data."""
        order = self.tm._construct_new_order(TradeState.NEW_BUY)
        self.assertIsNotNone(order)
        self.assertEqual(order.side, Side.BUY)
        self.assertEqual(order.side_str, "BUY")
        self.assertEqual(order.entry_price, 100_000.0)
        self.assertEqual(order.ticker_size, 0.01)
        self.assertEqual(order.quote_size, 100.0)
        self.assertFalse(order.meta_data.get("reverse", False))

    def test_new_sell_order_fields(self):
        """NEW_SELL → side=SELL, correct prices."""
        order = self.tm._construct_new_order(TradeState.NEW_SELL)
        self.assertIsNotNone(order)
        self.assertEqual(order.side, Side.SELL)
        self.assertEqual(order.side_str, "SELL")
        self.assertFalse(order.meta_data.get("reverse", False))

    def test_reverse_buy_uses_base_plus_position_size(self):
        """
        REVERSE_BUY with existing position → order_size = position_size + base_size.
        But PositionState stores only base_size (no exponential growth).
        """
        existing = _make_position(side=Side.SELL, ticker_size=0.01, quote_size=100.0)
        with self.tm.lock_current_position:
            self.tm.current_position = existing

        order = self.tm._construct_new_order(TradeState.REVERSE_BUY)
        self.assertIsNotNone(order)
        self.assertEqual(order.side, Side.BUY)
        # order_size = position(0.01) + base(0.01) = 0.02 (sent to exchange)
        self.assertEqual(order.ticker_size, 0.02)
        self.assertEqual(order.quote_size, 200.0)
        self.assertTrue(order.meta_data.get("reverse"))
        # base sizes stored in meta_data for _update_position
        self.assertEqual(order.meta_data["base_ticker_size"], 0.01)
        self.assertEqual(order.meta_data["base_quote_size"], 100.0)

    def test_reverse_sell_uses_base_plus_position_size(self):
        """REVERSE_SELL with existing position → order_size = position + base."""
        existing = _make_position(side=Side.BUY, ticker_size=0.05, quote_size=500.0)
        with self.tm.lock_current_position:
            self.tm.current_position = existing

        order = self.tm._construct_new_order(TradeState.REVERSE_SELL)
        self.assertIsNotNone(order)
        self.assertEqual(order.side, Side.SELL)
        # order_size = position(0.05) + base(0.01) = 0.06
        self.assertAlmostEqual(order.ticker_size, 0.06, places=5)
        # order quote = position(500) + base(100) = 600
        self.assertAlmostEqual(order.quote_size, 600.0, places=2)
        self.assertTrue(order.meta_data.get("reverse"))

    def test_reverse_without_position_uses_base_size(self):
        """REVERSE_BUY with no existing position → falls back to base sizing."""
        self.tm.current_position = None
        order = self.tm._construct_new_order(TradeState.REVERSE_BUY)
        self.assertIsNotNone(order)
        self.assertEqual(order.ticker_size, 0.01)    # base size, not 2x
        self.assertEqual(order.quote_size, 100.0)

    def test_consecutive_reverses_no_size_explosion(self):
        """
        Key test: consecutive REVERSE operations should NOT cause exponential size growth.
        After REVERSE, PositionState stores base_size, so next REVERSE is still base+base.
        """
        # Simulate: NEW_BUY → REVERSE_SELL → REVERSE_BUY
        # Step 1: NEW_BUY — position = base size
        order1 = self.tm._construct_new_order(TradeState.NEW_BUY)
        self.tm._update_position(order1, TradeState.NEW_BUY)
        self.assertEqual(self.tm.current_position.ticker_size, 0.01)  # base

        # Step 2: REVERSE_SELL — order to exchange = 0.01+0.01=0.02, but position = 0.01 (base)
        order2 = self.tm._construct_new_order(TradeState.REVERSE_SELL)
        self.assertEqual(order2.ticker_size, 0.02)  # sent to exchange
        self.tm._update_position(order2, TradeState.REVERSE_SELL)
        self.assertEqual(self.tm.current_position.ticker_size, 0.01)  # still base!

        # Step 3: REVERSE_BUY — still 0.01+0.01=0.02, NOT 0.02+0.02=0.04
        order3 = self.tm._construct_new_order(TradeState.REVERSE_BUY)
        self.assertEqual(order3.ticker_size, 0.02)  # NOT 0.04!
        self.tm._update_position(order3, TradeState.REVERSE_BUY)
        self.assertEqual(self.tm.current_position.ticker_size, 0.01)  # still base!

    def test_tp_sl_prices_set_for_long(self):
        """NEW_BUY order gets correct TP (above) and SL (below) entry."""
        order = self.tm._construct_new_order(TradeState.NEW_BUY)
        self.assertGreater(order.tp_price, order.entry_price)
        self.assertLess(order.sl_price, order.entry_price)

    def test_tp_sl_prices_set_for_short(self):
        """NEW_SELL order gets correct TP (below) and SL (above) entry."""
        order = self.tm._construct_new_order(TradeState.NEW_SELL)
        self.assertLess(order.tp_price, order.entry_price)
        self.assertGreater(order.sl_price, order.entry_price)

    # --- EXIT order construction ---

    def test_exit_order_closes_long_with_sell(self):
        """EXIT with LONG position → SELL to close, size = position size."""
        pos = _make_position(side=Side.BUY, ticker_size=0.05, quote_size=500.0, entry_price=95_000.0)
        with self.tm.lock_current_position:
            self.tm.current_position = pos

        order = self.tm._construct_new_order(TradeState.EXIT)
        self.assertIsNotNone(order)
        self.assertEqual(order.side, Side.SELL)
        self.assertEqual(order.side_str, "SELL")
        self.assertEqual(order.ticker_size, 0.05)
        self.assertEqual(order.quote_size, 500.0)
        self.assertEqual(order.tp_price, 0.0)
        self.assertEqual(order.sl_price, 0.0)
        self.assertTrue(order.meta_data.get("exit"))

    def test_exit_order_closes_short_with_buy(self):
        """EXIT with SHORT position → BUY to close."""
        pos = _make_position(side=Side.SELL, ticker_size=0.02, quote_size=200.0, entry_price=105_000.0)
        with self.tm.lock_current_position:
            self.tm.current_position = pos

        order = self.tm._construct_new_order(TradeState.EXIT)
        self.assertIsNotNone(order)
        self.assertEqual(order.side, Side.BUY)
        self.assertEqual(order.side_str, "BUY")
        self.assertEqual(order.ticker_size, 0.02)
        self.assertEqual(order.quote_size, 200.0)

    def test_exit_order_pnl_rate_positive_for_profit(self):
        """EXIT long at a higher price → positive pnl_rate."""
        pos = _make_position(side=Side.BUY, entry_price=95_000.0)
        with self.tm.lock_current_position:
            self.tm.current_position = pos
        # mark_price is 100_000 → profit for long
        order = self.tm._construct_new_order(TradeState.EXIT)
        pnl_rate = order.meta_data.get("pnl_rate", 0.0)
        self.assertGreater(pnl_rate, 0)  # (100000 - 95000) / 95000 ≈ 0.0526

    def test_exit_order_pnl_rate_negative_for_loss(self):
        """EXIT long at a lower price → negative pnl_rate."""
        pos = _make_position(side=Side.BUY, entry_price=105_000.0)
        with self.tm.lock_current_position:
            self.tm.current_position = pos
        # mark_price is 100_000 → loss for long
        order = self.tm._construct_new_order(TradeState.EXIT)
        pnl_rate = order.meta_data.get("pnl_rate", 0.0)
        self.assertLess(pnl_rate, 0)  # (100000 - 105000) / 105000 ≈ -0.0476

    def test_exit_without_position_returns_none(self):
        """EXIT with no position → raises internally, returns None."""
        self.tm.current_position = None
        order = self.tm._construct_new_order(TradeState.EXIT)
        self.assertIsNone(order)


# =============================================================================
# 6. _format_trade_message() Tests
# =============================================================================
class TestFormatTradeMessage(unittest.TestCase):
    """Test trade message formatting."""

    def setUp(self):
        self.tm = _make_trade_manager()

    def test_new_order_message(self):
        order = _make_order(meta_data={})
        msg = self.tm._format_trade_message(order)
        self.assertIn("BUY", msg)
        self.assertIn("new order", msg.lower())
        self.assertNotIn("reverse", msg.lower())

    def test_reverse_order_message(self):
        order = _make_order(meta_data={"reverse": True})
        msg = self.tm._format_trade_message(order)
        self.assertIn("reverse", msg.lower())

    def test_message_contains_prices(self):
        order = _make_order(entry_price=50000.0, tp_price=51000.0, sl_price=49000.0)
        msg = self.tm._format_trade_message(order)
        self.assertIn("50000.0", msg)
        self.assertIn("51000.0", msg)
        self.assertIn("49000.0", msg)

    def test_exit_message_contains_pnl_and_exit_label(self):
        """EXIT message shows P/L percentage and 'EXIT' label."""
        order = _make_order(
            side=Side.SELL,
            side_str="SELL",
            tp_price=0.0,
            sl_price=0.0,
            meta_data={"exit": True, "pnl_rate": 0.05},  # 5% profit
        )
        msg = self.tm._format_trade_message(order)
        self.assertIn("EXIT", msg)
        self.assertIn("5.0%", msg)
        self.assertIn("Profit", msg)

    def test_exit_message_shows_loss(self):
        """EXIT message shows loss when pnl_rate is negative."""
        order = _make_order(
            side=Side.BUY,
            side_str="BUY",
            tp_price=0.0,
            sl_price=0.0,
            meta_data={"exit": True, "pnl_rate": -0.03},  # 3% loss
        )
        msg = self.tm._format_trade_message(order)
        self.assertIn("EXIT", msg)
        self.assertIn("Loss", msg)
        self.assertIn("-3.0%", msg)
        # Leveraged P/L with 10x
        self.assertIn("-30.0%", msg)


# =============================================================================
# 7. _make_order() Tests
# =============================================================================
class TestMakeOrder(unittest.TestCase):
    """Test order placement and current_order update."""

    def setUp(self):
        self.tm = _make_trade_manager()

    def test_current_position_is_updated(self):
        """After _make_order, current_position should be set with base size."""
        order = _make_order()
        self.tm._make_order(order, trade_action=TradeState.NEW_BUY)
        self.assertIsNotNone(self.tm.current_position)
        self.assertEqual(self.tm.current_position.side, Side.BUY)
        self.assertEqual(self.tm.current_position.ticker_size, 0.01)

    def test_binance_client_order_called(self):
        """binance_client.order() must be called with the order."""
        order = _make_order()
        self.tm._make_order(order, trade_action=TradeState.NEW_BUY)
        self.tm.binance_client.order.assert_called_once_with(order=order)

    def test_make_order_raises_on_exchange_error(self):
        """If binance_client.order() raises, _make_order propagates the error."""
        self.tm.binance_client.order.side_effect = Exception("API error")
        order = _make_order()
        with self.assertRaises(Exception):
            self.tm._make_order(order)


# =============================================================================
# 8. _execute_trade() Tests
# =============================================================================
class TestExecuteTrade(unittest.TestCase):
    """Test the full trade execution flow."""

    def setUp(self):
        self.tm = _make_trade_manager()
        self.tm._get_mark_price = MagicMock(return_value=MarkPrice(
            timestamp=int(time.time() * 1000),
            source="test",
            ticker=TradePair(ticker="BTC", quote="USDT"),
            mark_price=100_000.0,
        ))
        self.tm._get_trade_quote_amt = MagicMock(return_value=100.0)
        self.tm._get_trade_ticker_amt = MagicMock(return_value=0.01)

    def test_hold_does_nothing(self):
        """HOLD → no order, no telegram message."""
        result = self.tm._execute_trade(TradeState.HOLD)
        self.assertIsNone(result)
        self.tm.binance_client.order.assert_not_called()
        self.tm.telegram_bot.send_text.assert_not_called()

    def test_new_buy_places_order_and_sends_message(self):
        """NEW_BUY → order constructed, placed, telegram notified."""
        self.tm._execute_trade(TradeState.NEW_BUY)
        self.tm.binance_client.order.assert_called_once()
        self.tm.telegram_bot.send_text.assert_called_once()

    def test_new_sell_places_order(self):
        """NEW_SELL → order constructed and placed."""
        self.tm._execute_trade(TradeState.NEW_SELL)
        self.tm.binance_client.order.assert_called_once()
        called_order = self.tm.binance_client.order.call_args
        self.assertEqual(called_order.kwargs["order"].side, Side.SELL)

    def test_current_position_updated_after_execution(self):
        """After _execute_trade(NEW_BUY), current_position is set."""
        self.tm._execute_trade(TradeState.NEW_BUY)
        self.assertIsNotNone(self.tm.current_position)
        self.assertEqual(self.tm.current_position.side, Side.BUY)
        self.assertEqual(self.tm.current_position.ticker_size, 0.01)

    def test_exit_clears_position(self):
        """After _execute_trade(EXIT), current_position is None."""
        pos = _make_position(side=Side.BUY, ticker_size=0.01, quote_size=100.0)
        with self.tm.lock_current_position:
            self.tm.current_position = pos

        self.tm._execute_trade(TradeState.EXIT)
        self.assertIsNone(self.tm.current_position)
        self.tm.binance_client.order.assert_called_once()
        self.tm.telegram_bot.send_text.assert_called_once()


# =============================================================================
# 9. _get_trade_ticker_amt() and _get_trade_quote_amt() Tests
# =============================================================================
class TestTradeSizing(unittest.TestCase):
    """Test position sizing calculations."""

    def setUp(self):
        self.tm = _make_trade_manager(leverage=10, trade_weight=0.1)

    def test_quote_amt_is_weight_of_balance(self):
        """quote_amt = available_balance * trade_weight"""
        self.tm._get_available_quote = MagicMock(return_value=10_000.0)
        result = self.tm._get_trade_quote_amt()
        self.assertEqual(result, 1_000.0)  # 10000 * 0.1

    def test_ticker_amt_formula(self):
        """ticker_amt = (leverage * quote_amt) / price"""
        self.tm._get_available_quote = MagicMock(return_value=10_000.0)
        result = self.tm._get_trade_ticker_amt(ticker_price=100_000.0)
        # (10 * 1000) / 100000 = 0.1
        self.assertEqual(result, 0.1)

    def test_ticker_amt_rounds_to_3_decimals(self):
        """Result is rounded to 3 decimal places."""
        self.tm._get_available_quote = MagicMock(return_value=7_777.0)
        result = self.tm._get_trade_ticker_amt(ticker_price=99_999.0)
        # (10 * 777.7) / 99999 = 0.07777077...
        self.assertEqual(result, round((10 * 777.7) / 99_999.0, 3))


# =============================================================================
# 10. _decide_to_make_trade() Tests
# =============================================================================
class TestDecideToMakeTrade(unittest.TestCase):
    """Test whether the account check allows new trades."""

    def setUp(self):
        self.tm = _make_trade_manager()

    def test_no_open_position_returns_true(self):
        """balance == available_balance → no position → True"""
        self.tm._get_account_info = MagicMock(return_value=AccountInformation(
            timestamp=int(time.time() * 1000),
            source="test",
            id="test_id",
            asset="USDT",
            balance=10_000.0,
            unrealized_pnl=0.0,
            available_balance=10_000.0,
        ))
        self.assertTrue(self.tm._decide_to_make_trade())

    def test_open_position_returns_false(self):
        """balance != available_balance → position exists → False"""
        self.tm._get_account_info = MagicMock(return_value=AccountInformation(
            timestamp=int(time.time() * 1000),
            source="test",
            id="test_id",
            asset="USDT",
            balance=10_000.0,
            unrealized_pnl=50.0,
            available_balance=9_000.0,
        ))
        self.assertFalse(self.tm._decide_to_make_trade())

    def test_exception_returns_false(self):
        """If account info fetch fails, returns False (safe default)."""
        self.tm._get_account_info = MagicMock(side_effect=Exception("Network error"))
        self.assertFalse(self.tm._decide_to_make_trade())


# =============================================================================
# 11. Integration-style: Score Accumulation → Trade Decision
# =============================================================================
class TestScoreToDecisionIntegration(unittest.TestCase):
    """Test the flow: accumulate score deltas → _decide_trade produces correct state."""

    def setUp(self):
        self.tm = _make_trade_manager(score_threashold=10)  # low threshold for testing

    def test_accumulate_buys_triggers_new_buy(self):
        """Enough BUY signals → score exceeds threshold → NEW_BUY."""
        # 3 x LONG_TERM_BUY (5 each) = 15 > threshold(10)
        for _ in range(3):
            delta = self.tm._calculate_signal_score_delta(TradeSignal.LONG_TERM_BUY)
            self.tm.trade_score += delta

        result = self.tm._decide_trade(self.tm.trade_score)
        self.assertEqual(result, TradeState.NEW_BUY)

    def test_accumulate_sells_triggers_new_sell(self):
        """Enough SELL signals → score below -threshold → NEW_SELL."""
        for _ in range(3):
            delta = self.tm._calculate_signal_score_delta(TradeSignal.LONG_TERM_SELL)
            self.tm.trade_score += delta

        result = self.tm._decide_trade(self.tm.trade_score)
        self.assertEqual(result, TradeState.NEW_SELL)

    def test_mixed_signals_stay_hold(self):
        """Balanced BUY and SELL signals → score near zero → HOLD."""
        self.tm.trade_score += self.tm._calculate_signal_score_delta(TradeSignal.LONG_TERM_BUY)   # +5
        self.tm.trade_score += self.tm._calculate_signal_score_delta(TradeSignal.LONG_TERM_SELL)  # -5
        # Net = 0

        result = self.tm._decide_trade(self.tm.trade_score)
        self.assertEqual(result, TradeState.HOLD)

    def test_hold_signal_no_score_change(self):
        """HOLD signal adds 0 to score."""
        initial = self.tm.trade_score
        delta = self.tm._calculate_signal_score_delta(TradeSignal.HOLD)
        self.tm.trade_score += delta
        self.assertEqual(self.tm.trade_score, initial)


# =============================================================================
# 12. Edge Cases & Boundary Tests
# =============================================================================
class TestEdgeCases(unittest.TestCase):
    """Boundary and edge-case tests."""

    def setUp(self):
        self.tm = _make_trade_manager(score_threashold=100)

    def test_threshold_boundary_plus_one(self):
        """score = threshold + 1 → NEW_BUY"""
        self.assertEqual(self.tm._decide_trade(101), TradeState.NEW_BUY)

    def test_threshold_boundary_exact(self):
        """score = threshold → HOLD (strict inequality)"""
        self.assertEqual(self.tm._decide_trade(100), TradeState.HOLD)

    def test_neg_threshold_boundary_minus_one(self):
        """score = -(threshold + 1) → NEW_SELL"""
        self.assertEqual(self.tm._decide_trade(-101), TradeState.NEW_SELL)

    def test_neg_threshold_boundary_exact(self):
        """score = -threshold → HOLD"""
        self.assertEqual(self.tm._decide_trade(-100), TradeState.HOLD)

    def test_construct_order_invalid_state_returns_none(self):
        """Invalid TradeState → _construct_new_order returns None (exception caught)."""
        self.tm._get_mark_price = MagicMock(return_value=MarkPrice(
            timestamp=0, source="t", ticker=TradePair("BTC", "USDT"), mark_price=100_000.0,
        ))
        result = self.tm._construct_new_order(TradeState.HOLD)
        self.assertIsNone(result)

    def test_order_copy_produces_equal_but_distinct_object(self):
        """Order.copy() returns a new object with identical fields."""
        order = _make_order()
        copied = order.copy()
        self.assertEqual(order, copied)
        self.assertIsNot(order, copied)

    def test_generate_timestamp_returns_ms(self):
        """Timestamp should be in milliseconds (13 digits approximately)."""
        ts = TradeManager.generate_timestamp()
        self.assertGreater(ts, 1_000_000_000_000)  # > 2001 in ms


# =============================================================================
# 13. Score Decay Tests
# =============================================================================
class TestScoreDecay(unittest.TestCase):
    """Test that trade_score decays over time via decay_rate."""

    def test_decay_reduces_positive_score(self):
        """Positive score should shrink after decay is applied."""
        tm = _make_trade_manager(score_decay_rate=0.9)
        tm.trade_score = 1000
        # Simulate one decay tick (what _thread_decide_trade does each loop)
        with tm.trade_score_lock:
            tm.trade_score = int(tm.trade_score * tm.score_decay_rate)
        self.assertEqual(tm.trade_score, 900)

    def test_decay_reduces_negative_score(self):
        """Negative score should shrink toward zero after decay."""
        tm = _make_trade_manager(score_decay_rate=0.9)
        tm.trade_score = -1000
        with tm.trade_score_lock:
            tm.trade_score = int(tm.trade_score * tm.score_decay_rate)
        self.assertEqual(tm.trade_score, -900)

    def test_decay_zero_stays_zero(self):
        """Score of 0 stays 0 after decay."""
        tm = _make_trade_manager(score_decay_rate=0.995)
        tm.trade_score = 0
        with tm.trade_score_lock:
            tm.trade_score = int(tm.trade_score * tm.score_decay_rate)
        self.assertEqual(tm.trade_score, 0)

    def test_decay_eventually_reaches_zero(self):
        """Repeated decay should bring score to 0."""
        tm = _make_trade_manager(score_decay_rate=0.5)
        tm.trade_score = 100
        for _ in range(20):
            tm.trade_score = int(tm.trade_score * tm.score_decay_rate)
        self.assertEqual(tm.trade_score, 0)

    def test_decay_rate_1_no_decay(self):
        """decay_rate=1.0 means no decay at all."""
        tm = _make_trade_manager(score_decay_rate=1.0)
        tm.trade_score = 500
        for _ in range(100):
            tm.trade_score = int(tm.trade_score * tm.score_decay_rate)
        self.assertEqual(tm.trade_score, 500)

    def test_default_decay_rate(self):
        """Default decay_rate should be 0.995."""
        tm = _make_trade_manager()
        self.assertEqual(tm.score_decay_rate, 0.995)


# =============================================================================
# 14. Trade Cooldown Tests
# =============================================================================
class TestTradeCooldown(unittest.TestCase):
    """Test the trade cooldown mechanism."""

    def test_default_cooldown_is_30s(self):
        """Default trade_cooldown_ms should be 30000."""
        tm = _make_trade_manager()
        self.assertEqual(tm.trade_cooldown_ms, 30_000)

    def test_last_trade_timestamp_starts_at_zero(self):
        """last_trade_timestamp should be 0 on init (no previous trade)."""
        tm = _make_trade_manager()
        self.assertEqual(tm.last_trade_timestamp, 0)

    def test_cooldown_allows_first_trade(self):
        """First trade should always pass cooldown check (last_trade_timestamp=0)."""
        tm = _make_trade_manager(trade_cooldown_ms=60_000)
        now = TradeManager.generate_timestamp()
        # Cooldown check: now - 0 > 60_000 → True (always, since now is ~epoch ms)
        self.assertGreater(now - tm.last_trade_timestamp, tm.trade_cooldown_ms)

    def test_cooldown_blocks_within_window(self):
        """Trade within cooldown window should be blocked."""
        tm = _make_trade_manager(trade_cooldown_ms=60_000)
        tm.last_trade_timestamp = TradeManager.generate_timestamp()  # just traded
        now = TradeManager.generate_timestamp()
        # now - last_trade should be < 60_000 (we just set it)
        self.assertLess(now - tm.last_trade_timestamp, tm.trade_cooldown_ms)

    def test_cooldown_allows_after_window(self):
        """Trade after cooldown window should be allowed."""
        tm = _make_trade_manager(trade_cooldown_ms=5_000)
        tm.last_trade_timestamp = TradeManager.generate_timestamp() - 10_000  # 10s ago
        now = TradeManager.generate_timestamp()
        self.assertGreater(now - tm.last_trade_timestamp, tm.trade_cooldown_ms)


if __name__ == "__main__":
    unittest.main()
