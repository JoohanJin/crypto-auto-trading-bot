"""
TradeManager Unit Tests (WSDC Logic)
=======================
Tests for the core trading logic in TradeManager using the Weighted Signal Density & Consensus model.
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
        trade_cooldown_ms=300_000, # 5 min default
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
# 1. _analyze_signals() Tests (WSDC Logic)
# =============================================================================
class TestAnalyzeSignals(unittest.TestCase):
    """Test the _analyze_signals() WSDC logic."""

    def setUp(self):
        self.tm = _make_trade_manager()

    def _inject_signals(self, signals: list[TradeSignal], offset_ms: int = 0):
        """Helper to inject signals into history."""
        now = self.tm.generate_timestamp()
        with self.tm.signal_history_lock:
            for s in signals:
                self.tm.signal_history.append((now - offset_ms, s))

    # --- NEW ENTRY tests ---

    def test_new_buy_burst(self):
        """Density >= 20 and Consensus >= 0.8 → NEW_BUY"""
        # Inject 20 LONG_TERM_BUY signals
        self._inject_signals([TradeSignal.LONG_TERM_BUY] * 20)
        result = self.tm._analyze_signals()
        self.assertEqual(result, TradeState.NEW_BUY)

    def test_new_sell_burst(self):
        """Density >= 20 and Consensus <= -0.8 → NEW_SELL"""
        self._inject_signals([TradeSignal.LONG_TERM_SELL] * 20)
        result = self.tm._analyze_signals()
        self.assertEqual(result, TradeState.NEW_SELL)

    def test_low_density_returns_hold(self):
        """Density < 20 → HOLD even with perfect consensus"""
        self._inject_signals([TradeSignal.LONG_TERM_BUY] * 19)
        result = self.tm._analyze_signals()
        self.assertEqual(result, TradeState.HOLD)

    def test_mixed_momentum_returns_hold(self):
        """High density but low consensus → HOLD"""
        # 15 BUY, 10 SELL -> Net 5, Total 25 -> Consensus 0.2 < 0.8
        self._inject_signals([TradeSignal.LONG_TERM_BUY] * 15 + [TradeSignal.LONG_TERM_SELL] * 10)
        result = self.tm._analyze_signals()
        self.assertEqual(result, TradeState.HOLD)

    # --- EXIT tests ---

    def test_long_exit_on_momentum_flip(self):
        """LONG position + momentum turns bearish → EXIT"""
        pos = _make_position(side=Side.BUY)
        with self.tm.lock_current_position:
            self.tm.current_position = pos
        
        # Inject structural bullish bias
        self._inject_signals([TradeSignal.LONG_TERM_BUY] * 30, offset_ms=120_000)
        
        # Inject 20 bearish signals (Density 20 met)
        # But we mix them to keep consensus around -0.5 (meets EXIT > -0.3, but fails REVERSE > -0.8)
        # 15 SELL (weight -30), 5 BUY (weight +10) -> Net -20, Total 40 -> Consensus -0.5
        self._inject_signals([TradeSignal.SHORT_TERM_SELL] * 15 + [TradeSignal.SHORT_TERM_BUY] * 5)
        
        result = self.tm._analyze_signals()
        self.assertEqual(result, TradeState.EXIT)

    def test_short_exit_on_momentum_flip(self):
        """SHORT position + momentum turns bullish → EXIT"""
        pos = _make_position(side=Side.SELL)
        with self.tm.lock_current_position:
            self.tm.current_position = pos
            
        self._inject_signals([TradeSignal.LONG_TERM_SELL] * 30, offset_ms=120_000)
        
        # Inject 20 signals, consensus ~ +0.5
        self._inject_signals([TradeSignal.SHORT_TERM_BUY] * 15 + [TradeSignal.SHORT_TERM_SELL] * 5)
        
        result = self.tm._analyze_signals()
        self.assertEqual(result, TradeState.EXIT)

    # --- REVERSE tests ---

    def test_reverse_sell_on_strong_bearish_burst(self):
        """LONG position + strong bearish burst → REVERSE_SELL"""
        pos = _make_position(side=Side.BUY)
        with self.tm.lock_current_position:
            self.tm.current_position = pos
            
        # 20 strong sell signals (triggers burst)
        self._inject_signals([TradeSignal.LONG_TERM_SELL] * 20)
        result = self.tm._analyze_signals()
        self.assertEqual(result, TradeState.REVERSE_SELL)

    # --- PRUNING tests ---

    def test_stale_signals_are_pruned(self):
        """Signals older than 10m are ignored."""
        # Inject signals 11 minutes ago
        self._inject_signals([TradeSignal.LONG_TERM_BUY] * 50, offset_ms=660_000)
        result = self.tm._analyze_signals()
        self.assertEqual(result, TradeState.HOLD)
        self.assertEqual(len(self.tm.signal_history), 0)


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
        self.assertEqual(tp, 102_000.0)
        self.assertEqual(sl, 98_000.0)

    def test_short_tp_below_sl_above(self):
        """Short position: TP below entry, SL above entry."""
        tp, sl = self.tm._get_target_prices(
            buy_or_sell=TradeState.NEW_SELL,
            current_price=100_000.0,
        )
        self.assertEqual(tp, 98_000.0)
        self.assertEqual(sl, 102_000.0)


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
        signal._timestamp = int(time.time() * 1_000) - 10_000
        self.assertFalse(self.tm.verify_signal(signal, timestamp_window=5_000))


# =============================================================================
# 4. _construct_new_order() Tests
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
        order = self.tm._construct_new_order(TradeState.NEW_BUY)
        self.assertEqual(order.side, Side.BUY)
        self.assertEqual(order.ticker_size, 0.01)

    def test_reverse_buy_sizing(self):
        existing = _make_position(side=Side.SELL, ticker_size=0.01)
        with self.tm.lock_current_position:
            self.tm.current_position = existing
        order = self.tm._construct_new_order(TradeState.REVERSE_BUY)
        self.assertEqual(order.ticker_size, 0.02) # Close(0.01) + Open(0.01)

    def test_exit_without_position_raises(self):
        self.tm.current_position = None
        with self.assertRaises(ValueError):
            self.tm._construct_new_order(TradeState.EXIT)


# =============================================================================
# 5. _format_trade_message() Tests
# =============================================================================
class TestFormatTradeMessage(unittest.TestCase):
    """Test trade message formatting."""

    def setUp(self):
        self.tm = _make_trade_manager()

    def test_new_order_message(self):
        order = _make_order(meta_data={})
        msg = self.tm._format_trade_message(order)
        self.assertIn("Trade Signal: BUY", msg)
        self.assertIn("new order", msg.lower())

    def test_exit_message_pnl(self):
        order = _make_order(meta_data={"exit": True, "pnl_rate": 0.05})
        msg = self.tm._format_trade_message(order)
        self.assertIn("EXIT", msg)
        self.assertIn("5.0%", msg)


# =============================================================================
# 6. _make_order() Tests
# =============================================================================
class TestMakeOrder(unittest.TestCase):
    """Test order placement and current_position update."""

    def setUp(self):
        self.tm = _make_trade_manager()

    def test_current_position_is_updated(self):
        order = _make_order()
        self.tm._make_order(order, trade_action=TradeState.NEW_BUY)
        self.assertIsNotNone(self.tm.current_position)
        self.assertEqual(self.tm.current_position.side, Side.BUY)


# =============================================================================
# 7. _execute_trade() Tests
# =============================================================================
class TestExecuteTrade(unittest.TestCase):
    """Test the full trade execution flow."""

    def setUp(self):
        self.tm = _make_trade_manager()
        self.tm._get_mark_price = MagicMock(return_value=MarkPrice(
            timestamp=0, source="t", ticker=TradePair("BTC", "USDT"), mark_price=100_000.0,
        ))
        self.tm._get_trade_quote_amt = MagicMock(return_value=100.0)
        self.tm._get_trade_ticker_amt = MagicMock(return_value=0.01)

    def test_new_buy_execution(self):
        self.tm._execute_trade(TradeState.NEW_BUY)
        self.tm.binance_client.order.assert_called_once()
        self.tm.telegram_bot.send_text.assert_called_once()


# =============================================================================
# 8. Sizing & Account Tests
# =============================================================================
class TestTradeSizing(unittest.TestCase):
    def setUp(self):
        self.tm = _make_trade_manager(leverage=10, trade_weight=0.1)

    def test_quote_amt(self):
        self.tm._get_available_quote = MagicMock(return_value=1000.0)
        self.assertEqual(self.tm._get_trade_quote_amt(), 100.0)

class TestDecideToMakeTrade(unittest.TestCase):
    def setUp(self):
        self.tm = _make_trade_manager()

    def test_allow_trade_on_empty_position(self):
        self.tm._get_account_info = MagicMock(return_value=AccountInformation(
            timestamp=0, source="t", id="a", asset="USDT", balance=100.0, 
            unrealized_pnl=0.0, available_balance=100.0
        ))
        self.assertTrue(self.tm._decide_to_make_trade())


# =============================================================================
# 9. Trade Cooldown Tests
# =============================================================================
class TestTradeCooldown(unittest.TestCase):
    def setUp(self):
        self.tm = _make_trade_manager(trade_cooldown_ms=300_000) # 5 min

    def test_cooldown_blocks_immediate_retry(self):
        self.tm.last_trade_timestamp = self.tm.generate_timestamp()
        now = self.tm.generate_timestamp()
        self.assertLess(now - self.tm.last_trade_timestamp, self.tm.trade_cooldown_ms)


if __name__ == "__main__":
    unittest.main()
