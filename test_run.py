import time
from src.backtesting.runner import BacktestRunner
from src.backtesting.data_loader import MockPathType

runner = BacktestRunner(data_dir="data/historical", path_type=MockPathType.OHLC)
runner.run()
