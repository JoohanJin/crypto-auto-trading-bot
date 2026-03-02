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
    def __init__(self, csv_path: str, path_type: MockPathType = MockPathType.OHLC):
        """
        DataLoader reads historical CSV klines and simulates a stream of Ticker DTOs.

        Since we have Daily data, we generate 4 data points per day to simulate intraday volatility.
        """
        self.csv_path = csv_path
        self.path_type = path_type
        self.data = pd.read_csv(csv_path)
        self.callbacks: list[Callable[[Ticker], None]] = []

        # Determine the mock time gap between the 4 intra-day ticks.
        # A day has 86,400,000 ms. We space the 4 ticks equally.
        self.intra_day_interval_ms = 86_400_000 // 4

    def register_callback(self, callback: Callable[[Ticker], None]):
        """Similar to how WebSocketInterface registers callbacks."""
        self.callbacks.append(callback)

    def run(self, mock_broker=None, time_manager=None):
        """
        Iterate through the CSV and push data to the registered callbacks.
        """
        trade_pair = TradePair(ticker="BTC", quote="USDT")

        # Start our synthetic timestamp at some epoch (e.g., Jan 1, 2023)
        synthetic_timestamp = 1672531200000

        for index, row in self.data.iterrows():
            prices = []
            if self.path_type == MockPathType.OHLC:
                prices = [row['open'], row['high'], row['low'], row['close']]
            else:  # OLHC
                prices = [row['open'], row['low'], row['high'], row['close']]

            for price in prices:
                # Increment by 1 second (1000ms) for each price point
                synthetic_timestamp += 1000

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

                # Small sleep to allow background threads (DataProcessor, TradeManager) to process this tick
                time.sleep(0.001)


if __name__ == "__main__":
    loader = DataLoader("data/historical/BTC_USDT-Day1_20230101_20260302.csv")
    print(f"Loaded {len(loader.data)} days of data.")
