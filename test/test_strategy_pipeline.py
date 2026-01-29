from __future__ import annotations

import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from core.models.constants import IndexType  # type: ignore
from core.models.indexes import Index  # type: ignore
from core.models.signal import TradeSignal  # type: ignore

try:
    from strategy import (  # type: ignore
        StrategyCondition,
        StrategyConfig,
        StrategyExecutor,
        StrategyFactory,
        StrategyFetcher,
    )
    from strategy_manager import StrategyManager  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    StrategyCondition = StrategyConfig = StrategyExecutor = StrategyFactory = StrategyFetcher = StrategyManager = None  # type: ignore[misc]


class StrategyFactoryTest(unittest.TestCase):
    def setUp(self) -> None:
        if StrategyFactory is None:
            self.skipTest("strategy modules unavailable")

    def test_build_all_filters_disabled(self) -> None:
        factory = StrategyFactory()
        raw_config = {
            "strategies": [
                {"name": "s1", "enabled": False},
                {
                    "name": "s2",
                    "enabled": True,
                    "indicators": [],
                    "conditions": [],
                    "signal_type": "HOLD",
                },
            ]
        }

        configs = factory.build_all(raw_config)

        self.assertEqual(len(configs), 1)
        self.assertEqual(configs[0].name, "s2")

    def test_build_parses_enums(self) -> None:
        factory = StrategyFactory()
        raw = {
            "name": "golden",
            "enabled": True,
            "indicators": ["SMA", "EMA"],
            "conditions": [],
            "signal_type": "HOLD",
            "signal_window": 1234,
            "verify_freshness": True,
        }

        cfg = factory.build(raw)

        self.assertEqual(cfg.indicators, [IndexType.SMA, IndexType.EMA])
        self.assertEqual(cfg.signal_type, TradeSignal.HOLD)
        self.assertEqual(cfg.signal_window, 1234)
        self.assertTrue(cfg.verify_freshness)


class StrategyFetcherTest(unittest.TestCase):
    def setUp(self) -> None:
        if StrategyFetcher is None:
            self.skipTest("strategy modules unavailable")

    def test_loads_valid_json(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as tmp:
            tmp.write('{"strategies": [{"name": "demo"}]}')
            tmp_path = Path(tmp.name)

        fetcher = StrategyFetcher(tmp_path)
        data = fetcher.load_strategies()

        self.assertIn("strategies", data)
        self.assertEqual(data["strategies"][0]["name"], "demo")

        tmp_path.unlink(missing_ok=True)

    def test_missing_file_returns_empty(self) -> None:
        fetcher = StrategyFetcher(Path("non-existent-file.json"))
        data = fetcher.load_strategies()
        self.assertEqual(data.get("strategies"), [])


class StrategyExecutorTest(unittest.TestCase):
    def setUp(self) -> None:
        if StrategyExecutor is None:
            self.skipTest("strategy modules unavailable")

    def test_execute_emits_signal_once_and_updates_timestamp(self) -> None:
        strategy = StrategyConfig(
            name="demo",
            enabled=True,
            indicators=[],
            verify_freshness=False,
            conditions=[],
            signal_type=TradeSignal.SHORT_TERM_BUY,
            signal_window=1000,
        )

        push_signal = mock.Mock()
        update_timestamp = mock.Mock()
        should_generate = mock.Mock(side_effect=[True, SystemExit("stop")])
        get_indicators = mock.Mock(return_value={})
        verify_index = mock.Mock(return_value=True)

        executor = StrategyExecutor(
            push_signal=push_signal,
            get_indicators=get_indicators,
            should_generate=should_generate,
            update_timestamp=update_timestamp,
            verify_index=verify_index,
            sleep_interval=0,
        )

        logic = mock.Mock(return_value=TradeSignal.SHORT_TERM_BUY)

        with mock.patch("time.sleep", return_value=None), self.assertRaises(SystemExit):
            executor.execute(strategy, logic)

        push_signal.assert_called_once()
        update_timestamp.assert_called_once_with("demo")
        logic.assert_called_once()


class StrategyManagerHelpersTest(unittest.TestCase):
    def setUp(self) -> None:
        if StrategyManager is None:
            self.skipTest("strategy manager unavailable")
        # Prevent __init__ from launching threads
        self.start_patcher = mock.patch.object(StrategyManager, "start", lambda self: None)
        self.start_patcher.start()
        self.addCleanup(self.start_patcher.stop)

        sma_index = Index(timestamp=1_000, index_type=IndexType.SMA, data={60: 10.0})  # type: ignore[arg-type]
        ema_index = Index(timestamp=1_000, index_type=IndexType.EMA, data={60: 12.0})  # type: ignore[arg-type]
        self.manager = StrategyManager(
            indicators={IndexType.SMA: sma_index, IndexType.EMA: ema_index, IndexType.PRICE: 12.0},
            indicators_lock=threading.Lock(),
            push_signal_callback=lambda s: None,
            signal_window=1_000,
        )

    def test_resolve_indicator_value_for_index_and_float(self) -> None:
        val_index = self.manager._resolve_indicator_value(self.manager.indicators, "SMA", 60)
        val_price = self.manager._resolve_indicator_value(self.manager.indicators, "PRICE")
        self.assertEqual(val_index, 10.0)
        self.assertEqual(val_price, 12.0)

    def test_evaluate_comparison_condition(self) -> None:
        condition = StrategyCondition(
            type="comparison",
            payload={
                "left": {"indicator": "SMA", "window": 60},
                "right": {"indicator": "PRICE"},
                "operator": "<",
            },
        )
        cfg = StrategyConfig(
            name="cmp",
            enabled=True,
            indicators=[IndexType.SMA, IndexType.PRICE],
            verify_freshness=False,
            conditions=[condition],
            signal_type=TradeSignal.SHORT_TERM_BUY,
            signal_window=1_000,
        )

        signal = self.manager._evaluate_condition(condition, self.manager.indicators, cfg)
        self.assertEqual(signal, TradeSignal.SHORT_TERM_BUY)

    def test_evaluate_divergence_condition(self) -> None:
        condition = StrategyCondition(
            type="divergence",
            payload={
                "left": {"indicator": "SMA", "window": 60},
                "right": {"indicator": "EMA", "window": 60},
                "threshold": 1.0,
                "operator": "abs_difference",
            },
        )
        cfg = StrategyConfig(
            name="div",
            enabled=True,
            indicators=[IndexType.SMA],
            verify_freshness=False,
            conditions=[condition],
            signal_type=TradeSignal.HOLD,
            signal_window=1_000,
        )

        signal = self.manager._evaluate_condition(condition, self.manager.indicators, cfg)
        self.assertEqual(signal, TradeSignal.HOLD)

    def test_should_generate_signal_respects_window(self) -> None:
        self.manager.signal_timestamps["demo"] = 1_000  # type: ignore[attr-defined]
        with mock.patch.object(StrategyManager, "generate_timestamp", return_value=2_000):
            allowed = self.manager._should_generate_signal("demo", signal_window=500)
            self.assertTrue(allowed)


if __name__ == "__main__":
    unittest.main()
