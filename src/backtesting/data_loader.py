import glob
import os
import time
from enum import Enum
from typing import Callable

import pandas as pd

from src.core.models.service_dto import Ticker
from src.core.models.trade import TradePair


class MockPathType(Enum):
    OHLC = 1  # Open -> High -> Low -> Close
    OLHC = 2  # Open -> Low -> High -> Close


class DataLoader:
    def __init__(self, data_dir: str, path_type: MockPathType = MockPathType.OHLC):
        """
        DataLoader reads historical CSV klines from a directory of Binance CSVs
        and simulates a stream of Ticker DTOs.
        """
        self.data_dir = data_dir
        self.path_type = path_type

        # Load all CSVs, sorting by filename to keep them chronological
        self.csv_files = sorted(glob.glob(os.path.join(data_dir, "BTCUSDT-15m-*.csv")))
        self.callbacks: list[Callable[[Ticker], None]] = []

        # 15m interval = 900,000 ms. We simulate 4 ticks per interval.
        self.intra_day_interval_ms = 900_000 // 4

    def register_callback(self, callback: Callable[[Ticker], None]):
        """Similar to how WebSocketInterface registers callbacks."""
        self.callbacks.append(callback)

    def run(self, mock_broker=None, time_manager=None):
        """
        Iterate through the CSV files and push data to the registered callbacks.
        """
        trade_pair = TradePair(ticker="BTC", quote="USDT")

        total_processed_rows = 0

        # Start with an arbitrary realistic epoch timestamp and increment continuously
        synthetic_timestamp = 1600000000000

        for csv_file in self.csv_files:
            # Columns: open_time, open, high, low, close, volume, close_time, quote_asset_volume, number_of_trades, taker_buy_base_asset_volume, taker_buy_quote_asset_volume, ignore
            df = pd.read_csv(csv_file, header=0, usecols=[0, 1, 2, 3, 4], names=['open_time', 'open', 'high', 'low', 'close'])

            for index, row in df.iterrows():
                prices = []
                if self.path_type == MockPathType.OHLC:
                    prices = [row['open'], row['high'], row['low'], row['close']]
                else:  # OLHC
                    prices = [row['open'], row['low'], row['high'], row['close']]

                for price in prices:
                    synthetic_timestamp += self.intra_day_interval_ms

                    # 1. Update global mock time
                    if time_manager:
                        time_manager.set_time(synthetic_timestamp)

                    # 2. Update the Mock Broker's current price so executions happen at this price
                    if mock_broker:
                        mock_broker.set_current_price(float(price))

                    # 3. Create Ticker DTO
                    ticker_dto = Ticker(
                        ticker=trade_pair,
                        price=float(price),
                        timestamp=synthetic_timestamp,
                        source="BACKTEST_MOCK"
                    )

                    # 4. Push to all listeners (DataCollector / DataPipeline)
                    for callback in self.callbacks:
                        callback(ticker_dto)

                    # --- SYNCHRONIZATION BARRIER ---
                    # Wait for data to flow through pipelines before advancing the custom mock time
                    import time as real_time
                    if hasattr(self, "runner"):
                        while not (
                            self.runner.data_manager.collector.price_fetch_buffer.empty() and
                            self.runner.data_pipeline.queue.empty() and
                            self.runner.signal_pipeline.signal_queue.empty()
                        ):
                            real_time.sleep(0.0001)

                        # Instant yield to let background threads finish calculations
                        real_time.sleep(0.0001)
                    else:
                        real_time.sleep(0.0001)

                total_processed_rows += 1

        print(f"DataLoader finished. Processed {total_processed_rows} 15m intervals.")


if __name__ == "__main__":
    loader = DataLoader("data/historical/")
    print(f"Loaded {len(loader.csv_files)} files.")
