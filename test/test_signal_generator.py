"""
SignalGenerator Unit Tests
==========================
Tests for the SignalGenerator component, focusing on:
1. Dependency Injection of StrategyManager.
2. Data consumption from DataPipeline.
3. Signal production to SignalPipeline.
4. Thread management and lifecycle.
"""
import unittest
from unittest.mock import MagicMock, patch

# Core Models & Interfaces
from src.core.models.index import Index, IndexType
from src.core.models.signal import Signal, TradeSignal
from src.integrations.telegram.telegram_bot_class import CustomTelegramBot
from src.interfaces.pipeline_interface import PipelineController
from src.strategy.strategy_manager import StrategyManager

# Components under test
from src.trading.signal_generator import SignalGenerator


class TestSignalGenerator(unittest.TestCase):
    def setUp(self):
        # Mock dependencies
        self.mock_data_pipeline = MagicMock(spec=PipelineController)
        self.mock_signal_pipeline = MagicMock(spec=PipelineController)
        self.mock_telegram_bot = MagicMock(spec=CustomTelegramBot)

        # Mock StrategyManager to verify DI
        self.mock_strategy_manager = MagicMock(spec=StrategyManager)

    def test_dependency_injection_strategy_manager(self):
        """Verify that StrategyManager can be injected."""
        with patch.object(SignalGenerator, 'start', return_value=None):
            sg = SignalGenerator(
                data_pipeline_controller=self.mock_data_pipeline,
                signal_pipeline_controller=self.mock_signal_pipeline,
                custom_telegram_bot=self.mock_telegram_bot,
                strategy_manager=self.mock_strategy_manager,
            )

            # Assert the injected instance is used
            self.assertIs(sg.strategy_manager, self.mock_strategy_manager)

            # Assert StrategyManager wasn't re-instantiated (implied by identity check,
            # but usually verified by ensuring 'new' call didn't happen if we mocked class)

    def test_default_strategy_manager_creation(self):
        """Verify that StrategyManager is created if not injected."""
        with patch.object(SignalGenerator, 'start', return_value=None):
            # We need to mock StrategyManager constructor to avoid real threads/config loading
            with patch('src.trading.signal_generator.StrategyManager') as MockSM:
                sg = SignalGenerator(
                    data_pipeline_controller=self.mock_data_pipeline,
                    signal_pipeline_controller=self.mock_signal_pipeline,
                    custom_telegram_bot=self.mock_telegram_bot,
                    strategy_manager=None,
                )

                # Assert a new StrategyManager was instantiated
                MockSM.assert_called_once()
                self.assertIsNotNone(sg.strategy_manager)

    def test_get_data_updates_indicators(self):
        """Verify get_data loop consumes from pipeline and updates indicators."""
        with patch.object(SignalGenerator, 'start', return_value=None):
            sg = SignalGenerator(
                data_pipeline_controller=self.mock_data_pipeline,
                signal_pipeline_controller=self.mock_signal_pipeline,
                custom_telegram_bot=self.mock_telegram_bot,
                strategy_manager=self.mock_strategy_manager,
            )

            # Setup data
            test_index = Index(timestamp=1000, index_type=IndexType.SMA, data={60: 100.0})

            # We want to test the body of the loop. Since it's a while True that catches Exception,
            # we will raise a BaseException (which is not caught by `except Exception:`) to break the loop.
            class StopLoopException(BaseException):
                pass

            self.mock_data_pipeline.pop.side_effect = [test_index, StopLoopException("Stop")]

            # Catch the exception we threw to break the loop
            with self.assertRaises(StopLoopException):
                sg.get_data()

            # Verify the indicator was updated
            self.assertEqual(sg.indicators[IndexType.SMA], test_index)

    def test_push_signal_delegates_to_pipeline(self):
        """Verify push_signal puts signal into the pipeline."""
        with patch.object(SignalGenerator, 'start', return_value=None):
            sg = SignalGenerator(
                data_pipeline_controller=self.mock_data_pipeline,
                signal_pipeline_controller=self.mock_signal_pipeline,
                custom_telegram_bot=self.mock_telegram_bot,
                strategy_manager=self.mock_strategy_manager,
            )

            test_signal = Signal(signal=TradeSignal.LONG_TERM_BUY)
            sg.push_signal(test_signal)

            self.mock_signal_pipeline.push.assert_called_once_with(test_signal)


if __name__ == "__main__":
    unittest.main()
