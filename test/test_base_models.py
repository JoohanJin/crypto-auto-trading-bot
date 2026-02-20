"""Test that all models correctly inherit copy() from base classes."""
import unittest
from src.core.models.trade import TradePair
from src.core.models.order import Order
from src.core.models.service_dto import Ping, Ticker
from src.core.models.price import Price
from src.core.models.score import ScoreMetrics
from src.core.models.trend import TrendState
from src.core.models.base import Side


class TestBaseModels(unittest.TestCase):
    def test_immutable_models(self):
        # TradePair
        tp = TradePair('BTC', 'USDT')
        tp_copy = tp.copy()
        self.assertIsInstance(tp_copy, TradePair)
        
        # Ping (ServiceDTO subclass)
        ping = Ping(timestamp=123, source='mexc', success=True)
        ping_copy = ping.copy()
        self.assertIsInstance(ping_copy, Ping)
        
        # Ticker (ServiceDTO subclass)
        ticker = Ticker(timestamp=123, source='binance', ticker=tp, price=50000.0)
        ticker_copy = ticker.copy()
        self.assertIsInstance(ticker_copy, Ticker)
        
        # Order
        order = Order(
            side=Side.BUY, side_str='BUY', leverage=10,
            entry_price=50000, tp_price=55000, sl_price=48000,
            ticker='BTC', ticker_size=0.001, quote='USDT', quote_size=50, meta_data=None,
            trade_pair=TradePair("BTC", "USDT"),
        )
        order_copy = order.copy()
        self.assertIsInstance(order_copy, Order)

    def test_mutable_models(self):
        tp = TradePair('BTC', 'USDT')
        
        # Price
        price = Price(timestamp=123, trading_pair=tp, price=50000.0)
        price_copy = price.copy()
        self.assertIsInstance(price_copy, Price)
        
        # ScoreMetrics
        score = ScoreMetrics(
            timestamp=123, current_score=0.5, trend=TrendState.BULLISH,
            velocity=0.1, acceleration=0.01, volatility=0.2, confidence=0.8
        )
        score_copy = score.copy()
        self.assertIsInstance(score_copy, ScoreMetrics)


if __name__ == "__main__":
    unittest.main()
