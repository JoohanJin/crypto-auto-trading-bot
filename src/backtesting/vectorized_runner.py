"""
Vectorized Backtesting Runner — v2
===================================
Improvements over v1:
  1.  PnL uses position size locked at entry (not current balance at close)
  2.  Signal scoring separates stacking strategies (golden_cross + ema_trend_follow)
      and computes EMA(60) independently; normalization divisor = 13
  3.  Hold-ratio veto (>=50 % HOLD ticks in short window suppresses entry)
  4.  ema/sma divergence HOLD scoring (|SMA60-EMA60|>0.02 → counted as HOLD for ratio)
  5.  Density minimum filter (struct >= 350, short >= 70)
  6.  Warm-up guard (skip first struct_window ticks explicitly)
  7.  Minimum trade-count filter in ranking (configs with < MIN_TRADES are penalized)
  8.  Risk metrics: max drawdown, win-rate reported
  9.  Trade cooldown (configurable ticks between trades; extended after panic exit)
  10. Numba @njit simulation loop (~50-100x faster)
  11. Walk-forward split (train 70 % / test 30 %) to detect overfitting
  12. Per-phase final PnL run printed after each optimization phase
  13. Optimal config exported to JSON

Volatility fix (v2.1):
  - Replaced rolling std/mean (7.5h window → 0.1-2% scale, non-transferable to live)
    with per-candle H-L range: (high - low) / close * 100
  - H-L% is computed once per 15m candle and broadcast to all 4 OHLC ticks
  - Produces 0.1-0.5% quiet / 0.5-2% volatile — same interpretable scale as
    the live system's intra-period price movement
  - Search range updated from [0.0, 0.10] to [0.0, 0.80] to match new scale

Bug-fix release (v2.2):
  - Open positions are now settled at end of simulation — previously the last
    trade's unrealized P&L was silently lost, biasing rankings and making the
    test set look artificially dead
  - Divergence threshold changed from absolute (0.02) to percentage-based
    (0.10 % of midpoint). The absolute threshold was almost always exceeded
    at higher prices (BTC 50-100k), pushing hold_ratio → 1.0 and blocking
    all entries in the test set (late-period high-price data)
  - MIN_TRADES raised from 20 → 50 to discourage ultra-sparse configs that
    overfit to a handful of lucky trades
"""

from __future__ import annotations

import glob
import itertools
import json
import os
import time
from enum import IntFlag
from pathlib import Path

import numpy as np
import pandas as pd
from numba import njit

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
INITIAL_BALANCE = 10_000.0
TRADE_WEIGHT = 0.15
LEVERAGE = 10
TAKER_FEE = 0.001
MIN_TRADES = 50          # minimum trades for a config to be ranked fairly
COOLDOWN_TICKS = 8       # ~2 hours of cooldown at 15-min/4-tick resolution
EXIT_COOLDOWN_TICKS = 40  # extended cooldown after panic exit (~10 hours)

# Signal scoring constants (matching live strategy weights)
WEIGHT_GOLDEN_CROSS = 5      # SMA60 > EMA300
WEIGHT_EMA_TREND = 5         # EMA60 > EMA300
WEIGHT_PRICE_VS_SMA = 3      # PRICE > SMA300
MAX_SIGNAL_SCORE = float(WEIGHT_GOLDEN_CROSS + WEIGHT_EMA_TREND + WEIGHT_PRICE_VS_SMA)  # 13

DIVERGENCE_THRESHOLD_PCT = 0.10  # |SMA60 - EMA60| / midpoint as %, for HOLD signal

# Window sizes (in ticks; 1 tick ≈ 3.75 min with 4x OHLC expansion)
SHORT_WINDOW = 120
MID_WINDOW = 300
STRUCT_WINDOW = 600

# Density minimums (matching live TradeManager)
MIN_STRUCT_DENSITY = 350
MIN_SHORT_DENSITY = 70


class TradeSignal(IntFlag):
    SHORT_TERM_BUY = 1 << 0
    LONG_TERM_BUY = 1 << 1
    SHORT_TERM_SELL = 1 << 2
    LONG_TERM_SELL = 1 << 3
    HOLD = 1 << 4


# ---------------------------------------------------------------------------
# Numba-accelerated simulation
# ---------------------------------------------------------------------------
@njit(cache=True)
def _simulate_core(
    prices: np.ndarray,
    c_short: np.ndarray,
    c_mid: np.ndarray,
    c_struct: np.ndarray,
    densities_short: np.ndarray,
    densities_struct: np.ndarray,
    hold_ratios: np.ndarray,
    volatilities: np.ndarray,
    # Config params (scalars for Numba compatibility)
    cs_thresh: float,
    cm_thresh: float,
    cst_thresh: float,
    vol_threshold: float,
    use_exit: bool,
    ex_short: float,
    ex_mid: float,
    ex_struct: float,
    # Simulation params
    initial_balance: float,
    trade_weight: float,
    leverage: int,
    taker_fee: float,
    cooldown_ticks: int,
    exit_cooldown_ticks: int,
    min_struct_density: float,
    min_short_density: float,
    warm_up_ticks: int,
) -> tuple[float, int, int, float, float]:
    """
    Returns: (final_pnl, total_trades, wins, max_drawdown_pct, final_balance)
    """
    balance = initial_balance
    peak_balance = initial_balance
    max_drawdown_pct = 0.0

    current_side = 0       # 0=flat, 1=long, -1=short
    entry_price = 0.0
    position_size = 0.0    # locked at entry time
    trades = 0
    wins = 0
    cooldown_remaining = 0

    n = len(prices)
    for i in range(n):
        # Warm-up guard
        if i < warm_up_ticks:
            continue

        # Cooldown
        if cooldown_remaining > 0:
            cooldown_remaining -= 1
            continue

        # Volatility chop filter
        is_volatile = volatilities[i] >= vol_threshold

        # Hold ratio veto
        if hold_ratios[i] >= 0.50:
            is_volatile = False  # suppress all entries in choppy conditions

        # Density filters
        has_density = (densities_struct[i] >= min_struct_density) and (densities_short[i] >= min_short_density)

        # Entry/Reverse conditions
        is_strong_buy = (
            is_volatile
            and has_density
            and c_short[i] >= cs_thresh
            and c_mid[i] >= cm_thresh
            and c_struct[i] >= cst_thresh
        )
        is_strong_sell = (
            is_volatile
            and has_density
            and c_short[i] <= -cs_thresh
            and c_mid[i] <= -cm_thresh
            and c_struct[i] <= -cst_thresh
        )

        # Exit conditions (flipped consensus)
        is_exit_long = False
        is_exit_short = False
        if use_exit:
            is_exit_long = (
                c_short[i] < -ex_short
                and c_mid[i] < -ex_mid
                and c_struct[i] < -ex_struct
            )
            is_exit_short = (
                c_short[i] > ex_short
                and c_mid[i] > ex_mid
                and c_struct[i] > ex_struct
            )

        if current_side == 0:
            if is_strong_buy:
                current_side = 1
                entry_price = prices[i]
                position_size = balance * trade_weight  # lock at entry
                trades += 1
                cooldown_remaining = cooldown_ticks
            elif is_strong_sell:
                current_side = -1
                entry_price = prices[i]
                position_size = balance * trade_weight
                trades += 1
                cooldown_remaining = cooldown_ticks

        elif current_side == 1:
            acted = False
            if is_strong_sell:  # REVERSE
                pnl = position_size * ((prices[i] - entry_price) / entry_price) * leverage
                fee = position_size * leverage * 2 * taker_fee
                balance += pnl - fee
                if pnl > 0:
                    wins += 1
                current_side = -1
                entry_price = prices[i]
                position_size = balance * trade_weight
                trades += 1
                cooldown_remaining = cooldown_ticks
                acted = True
            if not acted and use_exit and is_exit_long:  # PANIC EXIT
                pnl = position_size * ((prices[i] - entry_price) / entry_price) * leverage
                fee = position_size * leverage * taker_fee
                balance += pnl - fee
                if pnl > 0:
                    wins += 1
                current_side = 0
                trades += 1
                cooldown_remaining = exit_cooldown_ticks

        elif current_side == -1:
            acted = False
            if is_strong_buy:  # REVERSE
                pnl = position_size * ((entry_price - prices[i]) / entry_price) * leverage
                fee = position_size * leverage * 2 * taker_fee
                balance += pnl - fee
                if pnl > 0:
                    wins += 1
                current_side = 1
                entry_price = prices[i]
                position_size = balance * trade_weight
                trades += 1
                cooldown_remaining = cooldown_ticks
                acted = True
            if not acted and use_exit and is_exit_short:  # PANIC EXIT
                pnl = position_size * ((entry_price - prices[i]) / entry_price) * leverage
                fee = position_size * leverage * taker_fee
                balance += pnl - fee
                if pnl > 0:
                    wins += 1
                current_side = 0
                trades += 1
                cooldown_remaining = exit_cooldown_ticks

        # Track drawdown
        if balance > peak_balance:
            peak_balance = balance
        dd = (peak_balance - balance) / peak_balance * 100.0
        if dd > max_drawdown_pct:
            max_drawdown_pct = dd

    # ---- v2.2 fix: settle any open position at end of data ----
    # Previously the last trade's unrealized P&L was silently lost.
    if current_side == 1:
        pnl = position_size * ((prices[n - 1] - entry_price) / entry_price) * leverage
        fee = position_size * leverage * taker_fee
        balance += pnl - fee
        if pnl > 0:
            wins += 1
    elif current_side == -1:
        pnl = position_size * ((entry_price - prices[n - 1]) / entry_price) * leverage
        fee = position_size * leverage * taker_fee
        balance += pnl - fee
        if pnl > 0:
            wins += 1

    return balance - initial_balance, trades, wins, max_drawdown_pct, balance


# ---------------------------------------------------------------------------
# Main optimizer class
# ---------------------------------------------------------------------------
class HighResPeakOptimizer:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir

    # -----------------------------------------------------------------------
    # Data loading & feature engineering
    # -----------------------------------------------------------------------
    def load_and_signals(self) -> pd.DataFrame:
        print("[1/2] Vectorizing entire history with OHLC expansion (x4 data points)...")
        csv_files = sorted(glob.glob(os.path.join(self.data_dir, "BTCUSDT-15m-*.csv")))

        df_list = [
            pd.read_csv(
                f, header=0, usecols=[0, 1, 2, 3, 4],
                names=["timestamp", "open", "high", "low", "close"],
            )
            for f in csv_files
        ]
        df = pd.concat(df_list).sort_values("timestamp").reset_index(drop=True)

        # OHLC → 4 ticks per candle (open → low/high → high/low → close)
        bullish = df["close"] >= df["open"]
        tick1 = df["open"].values
        tick2 = np.where(bullish, df["low"].values, df["high"].values)
        tick3 = np.where(bullish, df["high"].values, df["low"].values)
        tick4 = df["close"].values

        prices_matrix = np.empty((len(df), 4))
        prices_matrix[:, 0] = tick1
        prices_matrix[:, 1] = tick2
        prices_matrix[:, 2] = tick3
        prices_matrix[:, 3] = tick4
        flat_prices = prices_matrix.flatten()

        expanded_df = pd.DataFrame({"price": flat_prices})
        expanded_df["price"] = expanded_df["price"] / 1_000
        print(f"[1/2] {expanded_df.shape[0]:,} expanded ticks loaded.")

        prices = expanded_df["price"].values

        # --- Indicators ---
        sma60 = expanded_df["price"].rolling(window=60).mean().values
        ema60 = expanded_df["price"].ewm(span=60, adjust=False).mean().values
        sma300 = expanded_df["price"].rolling(window=300).mean().values
        ema300 = expanded_df["price"].ewm(span=300, adjust=False).mean().values

        # --- Signal scoring (FIX #2: separate stacking strategies) ---
        n = len(prices)
        sig_scores = np.zeros(n)

        # golden_cross / death_cross: SMA60 vs EMA300  (weight ±5)
        sig_scores[sma60 > ema300] += WEIGHT_GOLDEN_CROSS
        sig_scores[sma60 < ema300] -= WEIGHT_GOLDEN_CROSS

        # ema_trend_follow: EMA60 vs EMA300  (weight ±5)
        sig_scores[ema60 > ema300] += WEIGHT_EMA_TREND
        sig_scores[ema60 < ema300] -= WEIGHT_EMA_TREND

        # price_moving_average: PRICE vs SMA300  (weight ±3)
        sig_scores[prices > sma300] += WEIGHT_PRICE_VS_SMA
        sig_scores[prices < sma300] -= WEIGHT_PRICE_VS_SMA

        # --- Consensus windows (normalized to [-1, +1]) ---
        def rolling_consensus(arr: np.ndarray, window: int) -> np.ndarray:
            return pd.Series(arr).rolling(window=window).mean().values / MAX_SIGNAL_SCORE

        expanded_df["c_short"] = rolling_consensus(sig_scores, SHORT_WINDOW)
        expanded_df["c_mid"] = rolling_consensus(sig_scores, MID_WINDOW)
        expanded_df["c_struct"] = rolling_consensus(sig_scores, STRUCT_WINDOW)

        # --- Density (non-zero signal ticks in window) ---
        non_zero = (sig_scores != 0).astype(float)
        expanded_df["density_struct"] = pd.Series(non_zero).rolling(window=STRUCT_WINDOW).sum().values
        expanded_df["density_short"] = pd.Series(non_zero).rolling(window=SHORT_WINDOW).sum().values

        # --- Hold ratio (FIX #3 & #4: include divergence HOLD) ---
        # A tick is "HOLD-like" when sig_scores==0 OR SMA/EMA diverge by > threshold %
        # v2.2 fix: use % of midpoint so the filter is consistent across the 10x
        # price range in the dataset (BTC $7k-$100k).
        midpoint = (sma60 + ema60) / 2.0
        relative_div = np.abs(sma60 - ema60) / np.where(midpoint > 0, midpoint, 1.0) * 100
        is_hold = ((sig_scores == 0) | (relative_div > DIVERGENCE_THRESHOLD_PCT)).astype(float)
        expanded_df["hold_ratio"] = pd.Series(is_hold).rolling(window=SHORT_WINDOW).mean().values

        # --- Volatility: rolling sliding-window H-L% (matches live system) ---
        # Live data_processor computes (max-min)/last_price*100 over a 600s (10min)
        # sliding window of tick prices. With 15m candles expanded to 4 ticks each,
        # 10 minutes ≈ 2.67 candles ≈ ~11 ticks. We use rolling max-min on the
        # expanded price series to replicate the same sliding-window behavior.
        VOL_WINDOW = 11  # ~10 minutes worth of expanded ticks
        rolling_max = pd.Series(prices).rolling(window=VOL_WINDOW).max()
        rolling_min = pd.Series(prices).rolling(window=VOL_WINDOW).min()
        expanded_df["volatility"] = ((rolling_max - rolling_min) / prices * 100).values

        result = expanded_df.dropna().reset_index(drop=True)
        vol_p25 = np.percentile(result["volatility"], 25)
        vol_p50 = np.percentile(result["volatility"], 50)
        vol_p75 = np.percentile(result["volatility"], 75)
        hr_p25 = np.percentile(result["hold_ratio"], 25)
        hr_p50 = np.percentile(result["hold_ratio"], 50)
        hr_p75 = np.percentile(result["hold_ratio"], 75)
        hr_below50 = (result["hold_ratio"] < 0.50).mean() * 100
        print(
            f"[2/2] {result.shape[0]:,} ticks after warm-up. "
            f"Signal scoring max weight ±{MAX_SIGNAL_SCORE:.0f}.\n"
            f"      Volatility (H-L%): p25={vol_p25:.3f}  p50={vol_p50:.3f}  p75={vol_p75:.3f}\n"
            f"      Hold ratio:  p25={hr_p25:.3f}  p50={hr_p50:.3f}  p75={hr_p75:.3f}  "
            f"(below 0.50 veto: {hr_below50:.1f}% of ticks)"
        )
        return result

    # -----------------------------------------------------------------------
    # Simulation wrapper (calls Numba core)
    # -----------------------------------------------------------------------
    def simulate(
        self,
        prices: np.ndarray,
        c_short: np.ndarray,
        c_mid: np.ndarray,
        c_struct: np.ndarray,
        densities_short: np.ndarray,
        densities_struct: np.ndarray,
        hold_ratios: np.ndarray,
        volatilities: np.ndarray,
        config: dict,
        use_exit: bool = False,
    ) -> tuple[float, int, int, float, float]:
        """Returns (pnl, trades, wins, max_drawdown_pct, final_balance)."""
        return _simulate_core(
            prices, c_short, c_mid, c_struct,
            densities_short, densities_struct, hold_ratios, volatilities,
            cs_thresh=config["c_short"],
            cm_thresh=config["c_mid"],
            cst_thresh=config["c_struct"],
            vol_threshold=config.get("vol_threshold", 0.0),
            use_exit=use_exit,
            ex_short=config.get("ex_short", 0.0),
            ex_mid=config.get("ex_mid", 0.0),
            ex_struct=config.get("ex_struct", 0.0),
            initial_balance=INITIAL_BALANCE,
            trade_weight=TRADE_WEIGHT,
            leverage=LEVERAGE,
            taker_fee=TAKER_FEE,
            cooldown_ticks=COOLDOWN_TICKS,
            exit_cooldown_ticks=EXIT_COOLDOWN_TICKS,
            min_struct_density=MIN_STRUCT_DENSITY,
            min_short_density=MIN_SHORT_DENSITY,
            warm_up_ticks=STRUCT_WINDOW,  # explicit warm-up guard
        )

    # -----------------------------------------------------------------------
    # Ranking metric (FIX #7: penalize low-trade configs)
    # -----------------------------------------------------------------------
    @staticmethod
    def _rank_key(result: tuple) -> float:
        """Rank configs by profit-per-trade, penalizing configs with fewer
        than MIN_TRADES and those with excessive trade counts.
        Goal: highest profit, fewest trades.
        Score = profit_per_trade * min(1, trades/MIN_TRADES)
          → below MIN_TRADES: hard ramp-up penalty
          → above MIN_TRADES: pure profit-per-trade (naturally rewards
            configs that achieve the same PnL with fewer trades)
        """
        pnl, trades = result[0], result[1]
        if trades <= 0:
            return -1e18
        ppt = pnl / trades
        trade_penalty = min(1.0, trades / MIN_TRADES)  # ramp 0→1
        return ppt * trade_penalty

    # -----------------------------------------------------------------------
    # Print helpers
    # -----------------------------------------------------------------------
    @staticmethod
    def _print_phase_result(
        label: str,
        config: dict,
        pnl: float,
        trades: int,
        wins: int,
        max_dd: float,
        final_bal: float,
        use_exit: bool,
    ) -> None:
        ppt = pnl / max(1, trades)
        win_rate = (wins / trades * 100) if trades > 0 else 0.0
        print(f"\n--- {label} ---")
        print(f"  Final Balance:  ${final_bal:,.2f}")
        print(f"  Total PnL:      ${pnl:+,.2f} ({pnl / INITIAL_BALANCE * 100:+.2f}%)")
        print(f"  Trades:         {trades}  |  Win Rate: {win_rate:.1f}%")
        print(f"  Profit/Trade:   ${ppt:+.2f}")
        print(f"  Max Drawdown:   {max_dd:.2f}%")
        print(f"  Entry:  c_short={config['c_short']:.3f}  c_mid={config['c_mid']:.3f}  c_struct={config['c_struct']:.3f}")
        print(f"  Volatility Threshold (H-L%): {config.get('vol_threshold', 0):.3f}%")
        if use_exit:
            print(f"  Exit:   ex_short={config.get('ex_short', 0):.3f}  ex_mid={config.get('ex_mid', 0):.3f}  ex_struct={config.get('ex_struct', 0):.3f}")

    def _run_and_print_final(
        self, label: str, config: dict, arrays: tuple, use_exit: bool,
    ) -> tuple[float, int, int, float, float]:
        """Run simulation with given config on provided arrays and print results."""
        prices, cs, cm, cst, ds, dst, hr, vols = arrays
        pnl, trades, wins, max_dd, final_bal = self.simulate(
            prices, cs, cm, cst, ds, dst, hr, vols, config, use_exit=use_exit,
        )
        self._print_phase_result(label, config, pnl, trades, wins, max_dd, final_bal, use_exit)
        return pnl, trades, wins, max_dd, final_bal

    # -----------------------------------------------------------------------
    # Main optimization
    # -----------------------------------------------------------------------
    def run(self) -> None:
        df = self.load_and_signals()

        all_arrays = (
            df["price"].values,
            df["c_short"].values,
            df["c_mid"].values,
            df["c_struct"].values,
            df["density_short"].values,
            df["density_struct"].values,
            df["hold_ratio"].values,
            df["volatility"].values,
        )

        # Walk-forward split (70 % train / 30 % test)
        n = len(df)
        split = int(n * 0.7)
        train_arrays = tuple(a[:split] for a in all_arrays)
        test_arrays = tuple(a[split:] for a in all_arrays)
        print(f"\nWalk-forward split: train={split:,} ticks, test={n - split:,} ticks")

        prices, cs, cm, cst, ds, dst, hr, vols = train_arrays

        # JIT warm-up (first call compiles; use a small throwaway run)
        print("\n[JIT] Compiling Numba kernel (one-time)...")
        jit_start = time.time()
        _ = self.simulate(prices[:1000], cs[:1000], cm[:1000], cst[:1000],
                          ds[:1000], dst[:1000], hr[:1000], vols[:1000],
                          {"c_short": 0.5, "c_mid": 0.5, "c_struct": 0.5, "vol_threshold": 0.0},
                          use_exit=False)
        print(f"[JIT] Compilation complete in {time.time() - jit_start:.2f}s.")

        # ===================================================================
        # PHASE 1: NO-EXIT optimization (Stages 1-2)
        # ===================================================================
        print("\n" + "=" * 80)
        print("PHASE 1: NO-EXIT OPTIMIZATION (Trend Reversal Only)")
        print("=" * 80)

        # Stage 1: Coarse entry + volatility search
        # Sliding-window H-L% scale: capped at ~p50 to prevent aggressive filtering.
        # Anything above median filters >50% of ticks, starving the strategy.
        # Sliding-window BTC 15m: p25~0.32%, p50~0.51%, p75~0.84%
        print("\n=== Stage 1: Coarse Entry & Volatility Search (0.1 step) ===")
        coarse_range = [round(x, 2) for x in np.arange(0.10, 1.01, 0.1)]
        vol_range = [round(x, 2) for x in np.arange(0.0, 0.55, 0.05)]
        coarse_combos = list(itertools.product(coarse_range, coarse_range, coarse_range, vol_range))

        results_coarse_entry: list[tuple] = []
        start = time.time()
        total = len(coarse_combos)
        print(f"Running {total:,} coarse simulations...")
        for i, (c1, c2, c3, v) in enumerate(coarse_combos):
            if i % 500 == 0:
                print(f"  Progress: {i:,}/{total:,} ...", flush=True)
            config = {"c_short": c1, "c_mid": c2, "c_struct": c3, "vol_threshold": v}
            pnl, trd, wins, dd, fb = self.simulate(prices, cs, cm, cst, ds, dst, hr, vols, config, use_exit=False)
            results_coarse_entry.append((pnl, trd, wins, dd, fb, config))

        results_coarse_entry.sort(key=self._rank_key, reverse=True)
        best_coarse_entry = results_coarse_entry[0][5]
        print(f"Stage 1 complete in {time.time() - start:.1f}s. Best: {best_coarse_entry}")

        # Stage 2: Fine entry search
        print("\n=== Stage 2: Fine Entry & Volatility Search (0.01 step) ===")

        COARSE_MIN = 0.10  # fine grid must not go below coarse grid minimum

        def get_fine_range(
            center: float,
            step: float = 0.01,
            spread: float = 0.05,
            floor: float = COARSE_MIN,
        ) -> list[float]:
            lo = max(floor, center - spread)
            hi = center + spread
            return [round(x, 3) for x in np.arange(lo, hi + step / 2, step)]

        fine_entry_combos = list(itertools.product(
            get_fine_range(best_coarse_entry["c_short"]),
            get_fine_range(best_coarse_entry["c_mid"]),
            get_fine_range(best_coarse_entry["c_struct"]),
            get_fine_range(best_coarse_entry["vol_threshold"], step=0.01, spread=0.05, floor=0.0),
        ))

        results_fine_entry: list[tuple] = []
        start = time.time()
        total = len(fine_entry_combos)
        print(f"Running {total:,} fine simulations...")
        for i, (c1, c2, c3, v) in enumerate(fine_entry_combos):
            if i % 1000 == 0:
                print(f"  Progress: {i:,}/{total:,} ...", flush=True)
            config = {"c_short": c1, "c_mid": c2, "c_struct": c3, "vol_threshold": v}
            pnl, trd, wins, dd, fb = self.simulate(prices, cs, cm, cst, ds, dst, hr, vols, config, use_exit=False)
            results_fine_entry.append((pnl, trd, wins, dd, fb, config))

        results_fine_entry.sort(key=self._rank_key, reverse=True)
        best_no_exit_cfg = results_fine_entry[0][5]
        print(f"Stage 2 complete in {time.time() - start:.1f}s. Best: {best_no_exit_cfg}")

        # Phase 1 final PnL: re-run best no-exit config on TRAIN set
        print("\n>>> PHASE 1 RESULT (TRAIN SET — No Exit) <<<")
        self._run_and_print_final("Train / No Exit", best_no_exit_cfg, train_arrays, use_exit=False)

        # Phase 1 final PnL: run best no-exit config on TEST set
        print("\n>>> PHASE 1 RESULT (TEST SET — No Exit) <<<")
        self._run_and_print_final("Test / No Exit", best_no_exit_cfg, test_arrays, use_exit=False)

        # ===================================================================
        # PHASE 2: WITH-EXIT optimization (Stages 3-4)
        # ===================================================================
        print("\n" + "=" * 80)
        print("PHASE 2: WITH-EXIT OPTIMIZATION (Panic Exit Enabled)")
        print("=" * 80)

        # Stage 3: Coarse exit search
        print("\n=== Stage 3: Coarse Exit Search (0.1 step) ===")
        exit_coarse_range = [round(x, 2) for x in np.arange(0.30, 1.01, 0.1)]
        exit_coarse_combos = list(itertools.product(exit_coarse_range, exit_coarse_range, exit_coarse_range))

        results_coarse_exit: list[tuple] = []
        start = time.time()
        for e1, e2, e3 in exit_coarse_combos:
            config = {**best_no_exit_cfg, "ex_short": e1, "ex_mid": e2, "ex_struct": e3}
            pnl, trd, wins, dd, fb = self.simulate(prices, cs, cm, cst, ds, dst, hr, vols, config, use_exit=True)
            results_coarse_exit.append((pnl, trd, wins, dd, fb, config))

        results_coarse_exit.sort(key=self._rank_key, reverse=True)
        best_coarse_exit = results_coarse_exit[0][5]
        print(
            f"Stage 3 complete in {time.time() - start:.1f}s. Coarse exit: "
            f"ex_short={best_coarse_exit['ex_short']}, ex_mid={best_coarse_exit['ex_mid']}, "
            f"ex_struct={best_coarse_exit['ex_struct']}"
        )

        # Stage 4: Fine exit search
        print("\n=== Stage 4: Fine Exit Search (0.01 step) ===")
        fine_exit_combos = list(itertools.product(
            get_fine_range(best_coarse_exit["ex_short"]),
            get_fine_range(best_coarse_exit["ex_mid"]),
            get_fine_range(best_coarse_exit["ex_struct"]),
        ))

        results_fine_exit: list[tuple] = []
        start = time.time()
        for e1, e2, e3 in fine_exit_combos:
            config = {**best_no_exit_cfg, "ex_short": e1, "ex_mid": e2, "ex_struct": e3}
            pnl, trd, wins, dd, fb = self.simulate(prices, cs, cm, cst, ds, dst, hr, vols, config, use_exit=True)
            results_fine_exit.append((pnl, trd, wins, dd, fb, config))

        results_fine_exit.sort(key=self._rank_key, reverse=True)
        best_exit_cfg = results_fine_exit[0][5]
        print(f"Stage 4 complete in {time.time() - start:.1f}s.")

        # Phase 2 final PnL: re-run best exit config on TRAIN set
        print("\n>>> PHASE 2 RESULT (TRAIN SET — With Exit) <<<")
        self._run_and_print_final("Train / With Exit", best_exit_cfg, train_arrays, use_exit=True)

        # Phase 2 final PnL: run best exit config on TEST set
        print("\n>>> PHASE 2 RESULT (TEST SET — With Exit) <<<")
        self._run_and_print_final("Test / With Exit", best_exit_cfg, test_arrays, use_exit=True)

        # ===================================================================
        # FINAL REPORT (full dataset)
        # ===================================================================
        print("\n" + "=" * 80)
        print("ULTIMATE SWEET SPOT REPORT  (v2 — Full Dataset)")
        print("=" * 80)

        print("\n🏆 OPTION 1: NO EXIT (Trend Reversal Only)")
        pnl1, trd1, w1, dd1, fb1 = self._run_and_print_final(
            "Full Dataset / No Exit", best_no_exit_cfg, all_arrays, use_exit=False,
        )

        print("\n🏆 OPTION 2: WITH EXIT (Panic Exit Enabled)")
        pnl2, trd2, w2, dd2, fb2 = self._run_and_print_final(
            "Full Dataset / With Exit", best_exit_cfg, all_arrays, use_exit=True,
        )

        ppt1 = pnl1 / max(1, trd1)
        ppt2 = pnl2 / max(1, trd2)
        if ppt1 >= ppt2:
            winner, winner_cfg, winner_exit = "NO EXIT", best_no_exit_cfg, False
            print("\n✅ CONCLUSION: 'NO EXIT' is superior (higher profit/trade).")
        else:
            winner, winner_cfg, winner_exit = "WITH EXIT", best_exit_cfg, True
            print("\n✅ CONCLUSION: 'WITH EXIT' is superior (higher profit/trade).")
        print(f"Winner: {winner}")
        print("=" * 80)

        # Export optimal config
        self._export_config(winner_cfg, winner_exit)

    # -----------------------------------------------------------------------
    # Export config to JSON
    # -----------------------------------------------------------------------
    @staticmethod
    def _export_config(config: dict, use_exit: bool) -> None:
        output = {
            "consensus_short_term_threshold": config["c_short"],
            "consensus_mid_term_threshold": config["c_mid"],
            "consensus_threshold": config["c_struct"],
            "volatility_threshold": config.get("vol_threshold", 0.0),
            "use_exit": use_exit,
        }
        if use_exit:
            output["exit_short_term_consensus_threshold"] = config.get("ex_short", 0.0)
            output["exit_mid_term_threshold"] = config.get("ex_mid", 0.0)
            output["exit_consensus_threshold"] = config.get("ex_struct", 0.0)

        out_path = Path("config") / "optimized_thresholds.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(output, f, indent=2)
        print(f"\n📁 Optimized thresholds saved to {out_path}")


if __name__ == "__main__":
    opt = HighResPeakOptimizer("data/historical")
    opt.run()
