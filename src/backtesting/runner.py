import time
from unittest.mock import MagicMock

from src.backtesting.data_loader import DataLoader, MockPathType
from src.backtesting.mock_broker import MockBinanceFutureHttpClient
# 1. Patch the time before importing any other modules that might save time references
from src.backtesting.time_manager import MockTimeManager, patch_system_time
from src.core.models.score_mapping import ScoreMapper
from src.core.models.trade import TradePair
from src.data.data_manager import DataManager
from src.integrations.telegram.telegram_bot_class import CustomTelegramBot
from src.interfaces.pipeline_interface import PipelineController
from src.pipeline.data_pipeline import DataPipeline
from src.pipeline.signal_pipeline import SignalPipeline
from src.trading.signal_generator import SignalGenerator
from src.trading.trade_manager import TradeManager
from src.strategy.strategy_manager import StrategyManager

patch_system_time()
TradeManager.verify_signal = lambda self, signal_data, timestamp_window=5000: True
StrategyManager._StrategyManager__verify_index = lambda self, index, time_window=5000: True

# Silence Heartbeat threads for speed
TradeManager._thread_log_status = lambda self: None
SignalGenerator._thread_log_status = lambda self: None
StrategyManager._thread_log_status = lambda self: None

# Core components


class BacktestRunner:
    def __init__(self, data_dir: str, path_type: MockPathType = MockPathType.OHLC):
        self.data_dir = data_dir
        self.path_type = path_type

        print("\n" + "="*50)
        print(f"INITIALIZING BACKTEST: {path_type.name}")
        print("="*50 + "\n")

        # Mock dependencies
        self.mock_broker = MockBinanceFutureHttpClient(initial_balance=10000.0)
        self.mock_telegram = MagicMock(spec=CustomTelegramBot)

        # 1. Create Pipelines
        self.data_pipeline = DataPipeline()
        self.signal_pipeline = SignalPipeline()

        self.data_controller = PipelineController(pipeline=self.data_pipeline)
        self.signal_controller = PipelineController(pipeline=self.signal_pipeline)

        # 2. Data Loader (Acts as the WebSocket)
        self.data_loader = DataLoader(data_dir=data_dir, path_type=path_type)
        self.data_loader.runner = self

        # We need a custom mock WebSocketInterface to inject the data_loader's callbacks
        class MockWebSocketInterface:
            def __init__(self, data_loader):
                self.data_loader = data_loader

            def ticker(self, callback):
                self.data_loader.register_callback(callback)

            def kline(self, callback, interval):
                pass

            def start(self):
                pass

        self.mock_wsi = MockWebSocketInterface(self.data_loader)

        # 3. Data Manager (Calculates SMA/EMA based on injected Tickers)
        self.data_manager = DataManager(
            websocket_interface=self.mock_wsi,
            pipeline_controller=self.data_controller,
            name="BACKTEST_DATA_MANAGER"
        )

        # 4. Signal Generator
        # In a backtest, the MA periods are normally in seconds (e.g. 10s, 60s, 300s).
        # We need to scale these to days since our ticks are 6-hours apart.
        # Wait, the MA_WRITE_PERIODS are hardcoded in constants.py as [10, 30, 60, 300, 600, 1200, 1800].
        # If DataProcessor uses these as seconds, and we feed 1 tick = 6 hours, it will break.
        # Let's override the MA_WRITE_PERIODS in DataProcessor if possible, or we scale our time ticks.
        # IF we want 1 day = 1 tick, but trick the bot into thinking 1 tick = 1 second.

        # Let's trick the bot! Instead of 1 tick = 6 hours of mock time,
        # let's make 1 tick = 1 second of mock time!
        # This way, the original MA_WRITE_PERIODS (10s, 60s, etc) work perfectly without modifying constants!
        # A day of CSV data (4 ticks) will represent 4 seconds of momentum in the bot's eyes.

        # Let's adjust DataLoader's tick interval directly here
        self.data_loader.intra_day_interval_ms = 1000  # 1 tick = 1 real second in bot time

        self.signal_generator = SignalGenerator(
            data_pipeline_controller=self.data_controller,
            signal_pipeline_controller=self.signal_controller,
            custom_telegram_bot=self.mock_telegram,
            name="BACKTEST_SIGNAL_GEN"
        )

        # 5. Trade Manager
        # Since 1 tick = 1 second, 10 minutes = 600 ticks.
        # 4 ticks per CSV day. 600 ticks = 150 days of data for the structural backbone.
        # We can tweak these to find the sweet spot!
        
        self.trade_manager = TradeManager(
            signal_pipeline_controller=self.signal_controller,
            http_interface=None,  # Mocked via binance_client
            binance_future_client=self.mock_broker,
            delta_mapper=ScoreMapper(),
            telegram_bot=self.mock_telegram,
            trade_pair=TradePair(ticker="BTC", quote="USDT"),
            leverage=10,
            trade_weight=0.15,
            history_window_ms=120_000,  # 120 ticks
            min_history_density=10,  # lowered so it can actually trigger with 6s cooldowns
            min_short_term_density=2, # lowered accordingly
            name="BACKTEST_TRADE_MANAGER"
        )

        # Start all (threads)
        # Note: DataManager and TradeManager already call start() in their __init__

    def run(self):
        print("\n[RUNNING] Pumping data...")
        start_real_time = time.time()

        # Blocking run
        self.data_loader.run(mock_broker=self.mock_broker, time_manager=MockTimeManager)

        end_real_time = time.time()
        print(f"[FINISHED] Processed {len(self.data_loader.csv_files)} files in {end_real_time - start_real_time:.2f} seconds.")
        self.analyze_performance()

    def analyze_performance(self):
        print("\n" + "="*50)
        print("BACKTEST PERFORMANCE REPORT")
        print("="*50)

        initial = self.mock_broker.initial_balance
        final = self.mock_broker.balance
        pnl = final - initial
        pnl_pct = (pnl / initial) * 100

        print(f"Initial Balance:  ${initial:,.2f}")
        print(f"Final Balance:    ${final:,.2f}")
        print(f"Total PnL:        ${pnl:,.2f} ({pnl_pct:+.2f}%)")
        print(f"Total Trades:     {len(self.mock_broker.trade_history)}")
        print("="*50 + "\n")


if __name__ == "__main__":
    import os
    data_dir = "data/historical"

    if not os.path.exists(data_dir):
        print("ERROR: Historical data directory not found!")
    else:
        # Run Test 1: OHLC
        runner_ohlc = BacktestRunner(data_dir=data_dir, path_type=MockPathType.OHLC)
        runner_ohlc.run()

        # Optional: Run Test 2: OLHC
        # runner_olhc = BacktestRunner(data_path=csv_path, path_type=MockPathType.OLHC)
        # runner_olhc.run()
