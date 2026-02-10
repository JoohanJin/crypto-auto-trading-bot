"""Test that all models correctly inherit copy() from base classes."""
from src.core.models.trade import TradePair
from src.core.models.order import Order, OrderType
from src.core.models.service_dto import Ping, Ticker, Kline
from src.core.models.price import Price
from src.core.models.score import ScoreMetrics
from src.core.models.trend import TrendState


def test_immutable_models():
    print("=== Testing ImmutableModel inheritance ===")
    
    # TradePair
    tp = TradePair('BTC', 'USDT')
    tp_copy = tp.copy()
    print(f"TradePair: {type(tp_copy).__name__}")
    assert type(tp_copy) == TradePair
    
    # Ping (ServiceDTO subclass)
    ping = Ping(timestamp=123, source='mexc', success=True)
    ping_copy = ping.copy()
    print(f"Ping: {type(ping_copy).__name__}")
    assert type(ping_copy) == Ping
    
    # Ticker (ServiceDTO subclass)
    ticker = Ticker(timestamp=123, source='binance', ticker=tp, last_price=50000.0)
    ticker_copy = ticker.copy()
    print(f"Ticker: {type(ticker_copy).__name__}")
    assert type(ticker_copy) == Ticker
    
    # Order
    order = Order(
        type=OrderType.BUY, type_str='BUY', leverage=10,
        entry_price=50000, tp_price=55000, sl_price=48000,
        ticker='BTC', ticker_size=0.001, quote='USDT', quote_size=50, meta_data=None
    )
    order_copy = order.copy()
    print(f"Order: {type(order_copy).__name__}")
    assert type(order_copy) == Order


def test_mutable_models():
    print("\n=== Testing MutableModel inheritance ===")
    
    tp = TradePair('BTC', 'USDT')
    
    # Price
    price = Price(timestamp=123, trading_pair=tp, price=50000.0)
    price_copy = price.copy()
    print(f"Price: {type(price_copy).__name__}")
    assert type(price_copy) == Price
    
    # ScoreMetrics
    score = ScoreMetrics(
        timestamp=123, current_score=0.5, trend=TrendState.BULLISH,
        velocity=0.1, acceleration=0.01, volatility=0.2, confidence=0.8
    )
    score_copy = score.copy()
    print(f"ScoreMetrics: {type(score_copy).__name__}")
    assert type(score_copy) == ScoreMetrics


if __name__ == "__main__":
    test_immutable_models()
    test_mutable_models()
    print("\n✅ All copy() methods return correct types!")
