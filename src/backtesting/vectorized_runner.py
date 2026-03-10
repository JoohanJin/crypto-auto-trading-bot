"""
Vectorized Backtesting Runner — v3.3
======================================
v3.3: Aligned consensus formula with live system
------------------------------------------------------------
Key change from v3.2:
  The consensus formula now matches the live SignalWindow exactly:
    consensus = net_weight / abs_weight
  where HOLD signals (weight=0) contribute 0 to BOTH numerator and denominator,
  effectively excluding themselves from the calculation.

  Previously (v3.2), consensus = rolling_mean(sig_scores) / 13, which caused
  HOLD-equivalent ticks to dilute consensus toward 0 — making thresholds
  non-transferable to the live system.

  HOLD signals are now generated from two sources (matching live):
  1. Volatility filter: when H-L% < vol_threshold → ALL signals become HOLD
  2. ema_sma_divergence: when |SMA-EMA| > threshold → emits additional HOLD

  Consensus and hold_ratio are computed INSIDE the Numba simulation loop using
  running sums, so vol_threshold (optimizer parameter) properly affects them
  on-the-fly without recomputing signal arrays for each threshold.

60-tick OHLC expansion (carried from v3.2):
  Each 1m candle is expanded to 60 synthetic ticks (~1 tick ≈ 1 second) using
  linear interpolation between OHLC pivot points.

Effective timescales (1 candle = 60 ticks):
  MA_SHORT_PERIOD = 60 × 60 = 3600 ticks = 60 min   (live: SMA/EMA 60s)
  MA_LONG_PERIOD  = 300 × 60 = 18000 ticks = 300 min (live: SMA/EMA 300s)
  SHORT_WINDOW    = 120 × 60 = 7200 ticks  = 2 h     (live: 2 min)
  MID_WINDOW      = 300 × 60 = 18000 ticks = 5 h     (live: 5 min)
  STRUCT_WINDOW   = 600 × 60 = 36000 ticks = 10 h    (live: 10 min)
  VOL_WINDOW      = 600 ticks = 10 min  ← tick-level, genuine improvement
  COOLDOWN_TICKS  = 30 ticks  = 30 s   ← tick-level, matches live exactly
  EXIT_COOLDOWN   = 600 ticks = 10 min ← tick-level, matches live exactly
"""

from __future__ import annotations

import glob
import itertools
import json
import os
import time
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
MIN_TRADES = 50

MAX_MONTHS = 6

TICKS_PER_CANDLE = 4

COOLDOWN_TICKS = 2
EXIT_COOLDOWN_TICKS = 40

WEIGHT_GOLDEN_CROSS = 5
WEIGHT_EMA_TREND = 5
WEIGHT_PRICE_VS_SMA = 3
MAX_SIGNAL_SCORE = float(WEIGHT_GOLDEN_CROSS + WEIGHT_EMA_TREND + WEIGHT_PRICE_VS_SMA)  # 13

DIVERGENCE_THRESHOLD_PCT = 0.10

MA_SHORT_PERIOD = 60 * TICKS_PER_CANDLE
MA_LONG_PERIOD = 300 * TICKS_PER_CANDLE

SHORT_WINDOW = 120 * TICKS_PER_CANDLE
MID_WINDOW = 300 * TICKS_PER_CANDLE
STRUCT_WINDOW = 600 * TICKS_PER_CANDLE

VOL_WINDOW = 40

MIN_STRUCT_DENSITY = 350
MIN_SHORT_DENSITY = 70


def _expand_ohlc_to_ticks(opens: np.ndarray, highs: np.ndarray,
                          lows: np.ndarray, closes: np.ndarray) -> np.ndarray:
    """Expand N OHLC candles to N*4 ticks: Open, High/Low, Low/High, Close (direction-aware)."""
    is_bullish = closes >= opens
    tick2 = np.where(is_bullish, lows,  highs)
    tick3 = np.where(is_bullish, highs, lows)

    prices = np.empty((len(opens), 4))
    prices[:, 0] = opens
    prices[:, 1] = tick2
    prices[:, 2] = tick3
    prices[:, 3] = closes
    return prices.ravel()


# ---------------------------------------------------------------------------
# Numba-accelerated simulation — v3.3
# consensus = net_weight / abs_weight (matching live SignalWindow)
# HOLD injection from vol_threshold and divergence, computed per-tick
# ---------------------------------------------------------------------------
@njit(cache=True)
def _simulate_core(
    prices: np.ndarray,
    tick_net_raw: np.ndarray,
    tick_abs_raw: np.ndarray,
    tick_div_hold: np.ndarray,
    densities_short: np.ndarray,
    densities_struct: np.ndarray,
    volatilities: np.ndarray,
    # Config params
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
    short_window: int,
    mid_window: int,
    struct_window: int,
) -> tuple[float, int, int, float, float]:
    """Returns: (final_pnl, total_trades, wins, max_drawdown_pct, final_balance)"""
    balance = initial_balance
    peak_balance = initial_balance
    max_drawdown_pct = 0.0

    current_side = 0
    entry_price = 0.0
    position_size = 0.0
    trades = 0
    wins = 0
    cooldown_remaining = 0

    n = len(prices)

    # Running sums for 3 consensus windows
    s_net = 0.0
    s_abs = 0.0
    s_hold = 0.0
    m_net = 0.0
    m_abs = 0.0
    m_hold = 0.0
    t_net = 0.0
    t_abs = 0.0
    t_hold = 0.0

    for i in range(n):
        # --- Compute this tick's effective values based on vol_threshold ---
        if volatilities[i] >= vol_threshold:
            net_i = tick_net_raw[i]
            abs_i = tick_abs_raw[i]
            hold_i = tick_div_hold[i]
        else:
            net_i = 0.0
            abs_i = 0.0
            hold_i = 3.0 + tick_div_hold[i]

        # --- Update running sums: add tick i ---
        s_net += net_i
        s_abs += abs_i
        s_hold += hold_i
        m_net += net_i
        m_abs += abs_i
        m_hold += hold_i
        t_net += net_i
        t_abs += abs_i
        t_hold += hold_i

        # --- Evict oldest tick from each window (recompute effective values) ---
        if i >= short_window:
            j = i - short_window
            if volatilities[j] >= vol_threshold:
                s_net -= tick_net_raw[j]
                s_abs -= tick_abs_raw[j]
                s_hold -= tick_div_hold[j]
            else:
                s_hold -= 3.0 + tick_div_hold[j]

        if i >= mid_window:
            j = i - mid_window
            if volatilities[j] >= vol_threshold:
                m_net -= tick_net_raw[j]
                m_abs -= tick_abs_raw[j]
                m_hold -= tick_div_hold[j]
            else:
                m_hold -= 3.0 + tick_div_hold[j]

        if i >= struct_window:
            j = i - struct_window
            if volatilities[j] >= vol_threshold:
                t_net -= tick_net_raw[j]
                t_abs -= tick_abs_raw[j]
                t_hold -= tick_div_hold[j]
            else:
                t_hold -= 3.0 + tick_div_hold[j]

        # --- Skip warm-up ---
        if i < warm_up_ticks:
            continue

        if cooldown_remaining > 0:
            cooldown_remaining -= 1
            continue

        # --- Compute consensus (matching live: net/abs) ---
        c_s = s_net / s_abs if s_abs > 0.0 else 0.0
        c_m = m_net / m_abs if m_abs > 0.0 else 0.0
        c_t = t_net / t_abs if t_abs > 0.0 else 0.0

        # --- Hold ratio from SHORT window ---
        hold_ratio = s_hold / densities_short[i] if densities_short[i] > 0.0 else 0.0

        # --- Density check ---
        has_density = (
            densities_struct[i] >= min_struct_density
            and densities_short[i] >= min_short_density
        )

        # --- Hold ratio veto ---
        if hold_ratio >= 0.50:
            has_density = False

        # --- Entry / exit signals ---
        is_strong_buy = (
            has_density
            and c_s >= cs_thresh
            and c_m >= cm_thresh
            and c_t >= cst_thresh
        )
        is_strong_sell = (
            has_density
            and c_s <= -cs_thresh
            and c_m <= -cm_thresh
            and c_t <= -cst_thresh
        )

        is_exit_long = False
        is_exit_short = False
        if use_exit and has_density:
            is_exit_long = (
                c_s < -ex_short
                and c_m < -ex_mid
                and c_t < -ex_struct
            )
            is_exit_short = (
                c_s > ex_short
                and c_m > ex_mid
                and c_t > ex_struct
            )

        # --- Trading logic (unchanged from v3.2) ---
        if current_side == 0:
            if is_strong_buy:
                current_side = 1
                entry_price = prices[i]
                position_size = balance * trade_weight
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
            if is_strong_sell:
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
            if not acted and use_exit and is_exit_long:
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
            if is_strong_buy:
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
            if not acted and use_exit and is_exit_short:
                pnl = position_size * ((entry_price - prices[i]) / entry_price) * leverage
                fee = position_size * leverage * taker_fee
                balance += pnl - fee
                if pnl > 0:
                    wins += 1
                current_side = 0
                trades += 1
                cooldown_remaining = exit_cooldown_ticks

        if balance > peak_balance:
            peak_balance = balance
        dd = (peak_balance - balance) / peak_balance * 100.0
        if dd > max_drawdown_pct:
            max_drawdown_pct = dd

    # Settle open position at end of data
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
    # Data loading & feature engineering — v3.3
    # -----------------------------------------------------------------------
    def load_and_signals(self) -> pd.DataFrame:
        # 1. Load the most recent MAX_MONTHS monthly 1m CSV files
        all_files = sorted(glob.glob(os.path.join(self.data_dir, "BTCUSDT-1m-*.csv")))
        csv_files = all_files[-MAX_MONTHS:]
        print(
            f"[1/3] Loading {len(csv_files)} months of 1m history "
            f"(last {MAX_MONTHS} of {len(all_files)} available)..."
        )

        df_list = [
            pd.read_csv(
                f, header=0, usecols=[0, 1, 2, 3, 4],
                names=["timestamp", "open", "high", "low", "close"],
            )
            for f in csv_files
        ]
        df = pd.concat(df_list).sort_values("timestamp").reset_index(drop=True)
        n_candles = len(df)
        print(f"[1/3] {n_candles:,} 1m candles. Expanding to {n_candles * TICKS_PER_CANDLE:,} ticks (OHLC)...")

        # 2. 4-tick OHLC expansion
        scale = 1_000.0
        prices = _expand_ohlc_to_ticks(
            df["open"].values / scale,
            df["high"].values / scale,
            df["low"].values / scale,
            df["close"].values / scale,
        )
        n = len(prices)
        prices_s = pd.Series(prices)

        print(f"[2/3] Computing indicators on {n:,} synthetic ticks...")

        # 3. Indicators
        sma_short = prices_s.rolling(window=MA_SHORT_PERIOD).mean().values
        ema_short = prices_s.ewm(span=MA_SHORT_PERIOD, adjust=False).mean().values
        sma_long = prices_s.rolling(window=MA_LONG_PERIOD).mean().values
        ema_long = prices_s.ewm(span=MA_LONG_PERIOD, adjust=False).mean().values

        # --- Per-strategy weights (matching live ScoreMapper) ---
        gc_weight = np.where(sma_short > ema_long,  WEIGHT_GOLDEN_CROSS,
                             np.where(sma_short < ema_long, -WEIGHT_GOLDEN_CROSS, 0.0))
        et_weight = np.where(ema_short > ema_long,  WEIGHT_EMA_TREND,
                             np.where(ema_short < ema_long, -WEIGHT_EMA_TREND, 0.0))
        pm_weight = np.where(prices > sma_long,  WEIGHT_PRICE_VS_SMA,
                             np.where(prices < sma_long, -WEIGHT_PRICE_VS_SMA, 0.0))

        # Tick-level aggregates for Numba
        tick_net_raw = gc_weight + et_weight + pm_weight    # signed sum
        tick_abs_raw = np.abs(gc_weight) + np.abs(et_weight) + np.abs(pm_weight)

        # ema_sma_divergence HOLD flag
        midpoint = (sma_short + ema_short) / 2.0
        relative_div = np.abs(sma_short - ema_short) / np.where(midpoint > 0, midpoint, 1.0) * 100
        tick_div_hold = (relative_div > DIVERGENCE_THRESHOLD_PCT).astype(np.float64)

        # Density: signal count per tick (vol-independent: 3 strategies + 0-1 divergence)
        sig_count_per_tick = 3.0 + tick_div_hold
        density_short = pd.Series(sig_count_per_tick).rolling(window=SHORT_WINDOW).sum().values
        density_struct = pd.Series(sig_count_per_tick).rolling(window=STRUCT_WINDOW).sum().values

        # Volatility: rolling H-L% over VOL_WINDOW ticks
        rolling_high = prices_s.rolling(window=VOL_WINDOW).max()
        rolling_low = prices_s.rolling(window=VOL_WINDOW).min()
        volatility = ((rolling_high - rolling_low) / prices_s * 100).values

        result = pd.DataFrame({
            "price":          prices,
            "tick_net_raw":   tick_net_raw,
            "tick_abs_raw":   tick_abs_raw,
            "tick_div_hold":  tick_div_hold,
            "density_short":  density_short,
            "density_struct": density_struct,
            "volatility":     volatility,
        }).dropna().reset_index(drop=True)

        vol_p25 = np.percentile(result["volatility"], 25)
        vol_p50 = np.percentile(result["volatility"], 50)
        vol_p75 = np.percentile(result["volatility"], 75)
        dh_pct = result["tick_div_hold"].mean() * 100
        print(
            f"[3/3] {result.shape[0]:,} ticks after warm-up.\n"
            f"      Volatility (H-L% / {VOL_WINDOW}s rolling): "
            f"p25={vol_p25:.3f}  p50={vol_p50:.3f}  p75={vol_p75:.3f}\n"
            f"      Divergence HOLD ticks: {dh_pct:.1f}%"
        )
        return result

    # -----------------------------------------------------------------------
    # Simulation wrapper — v3.3
    # -----------------------------------------------------------------------
    def simulate(
        self,
        prices: np.ndarray,
        tick_net_raw: np.ndarray,
        tick_abs_raw: np.ndarray,
        tick_div_hold: np.ndarray,
        densities_short: np.ndarray,
        densities_struct: np.ndarray,
        volatilities: np.ndarray,
        config: dict,
        use_exit: bool = False,
    ) -> tuple[float, int, int, float, float]:
        """Returns (pnl, trades, wins, max_drawdown_pct, final_balance)."""
        return _simulate_core(
            prices, tick_net_raw, tick_abs_raw, tick_div_hold,
            densities_short, densities_struct, volatilities,
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
            warm_up_ticks=STRUCT_WINDOW,
            short_window=SHORT_WINDOW,
            mid_window=MID_WINDOW,
            struct_window=STRUCT_WINDOW,
        )

    # -----------------------------------------------------------------------
    # Ranking metric
    # -----------------------------------------------------------------------
    @staticmethod
    def _rank_key(result: tuple) -> float:
        pnl = result[0]
        return pnl

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
        p, tnr, tar, tdh, ds, dst, vols = arrays
        pnl, trades, wins, max_dd, final_bal = self.simulate(
            p, tnr, tar, tdh, ds, dst, vols, config, use_exit=use_exit,
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
            df["tick_net_raw"].values,
            df["tick_abs_raw"].values,
            df["tick_div_hold"].values,
            df["density_short"].values,
            df["density_struct"].values,
            df["volatility"].values,
        )

        n = len(df)
        split = int(n * 0.7)
        train_arrays = tuple(a[:split] for a in all_arrays)
        test_arrays = tuple(a[split:] for a in all_arrays)
        print(f"\nWalk-forward split: train={split:,} ticks, test={n - split:,} ticks")

        p, tnr, tar, tdh, ds, dst, vols = train_arrays

        print("\n[JIT] Compiling Numba kernel (one-time)...")
        jit_start = time.time()
        _ = self.simulate(p[:2000], tnr[:2000], tar[:2000], tdh[:2000],
                          ds[:2000], dst[:2000], vols[:2000],
                          {"c_short": 0.5, "c_mid": 0.5, "c_struct": 0.5, "vol_threshold": 0.0},
                          use_exit=False)
        print(f"[JIT] Compilation complete in {time.time() - jit_start:.2f}s.")

        # ===================================================================
        # PHASE 1: NO-EXIT optimization (Stages 1-2)
        # ===================================================================
        print("\n" + "=" * 80)
        print("PHASE 1: NO-EXIT OPTIMIZATION (Trend Reversal Only)")
        print("=" * 80)

        # vol_threshold fixed at 0.0 — no volatility filter
        VOL_THRESHOLD = 0.0

        print("\n=== Stage 1: Entry Search (0.05 step) ===")
        coarse_range = [round(x, 2) for x in np.arange(0.50, 1.01, 0.05)]
        coarse_combos = list(itertools.product(coarse_range, coarse_range, coarse_range))

        results_coarse_entry: list[tuple] = []
        start = time.time()
        total = len(coarse_combos)
        print(f"Running {total:,} coarse simulations...")
        for i, (c1, c2, c3) in enumerate(coarse_combos):
            if i % 500 == 0:
                print(f"  Progress: {i:,}/{total:,} ...", flush=True)
            config = {"c_short": c1, "c_mid": c2, "c_struct": c3, "vol_threshold": VOL_THRESHOLD}
            pnl, trd, wins, dd, fb = self.simulate(p, tnr, tar, tdh, ds, dst, vols, config, use_exit=False)
            results_coarse_entry.append((pnl, trd, wins, dd, fb, config))

        results_coarse_entry.sort(key=self._rank_key, reverse=True)
        best_coarse_entry = results_coarse_entry[0][5]
        print(f"Stage 1 complete in {time.time() - start:.1f}s. Best: {best_coarse_entry}")

        print("\n=== Stage 2: Fine Entry Search (0.01 step) ===")

        COARSE_MIN = 0.50

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
        ))

        results_fine_entry: list[tuple] = []
        start = time.time()
        total = len(fine_entry_combos)
        print(f"Running {total:,} fine simulations...")
        for i, (c1, c2, c3) in enumerate(fine_entry_combos):
            if i % 200 == 0:
                print(f"  Progress: {i:,}/{total:,} ...", flush=True)
            config = {"c_short": c1, "c_mid": c2, "c_struct": c3, "vol_threshold": VOL_THRESHOLD}
            pnl, trd, wins, dd, fb = self.simulate(p, tnr, tar, tdh, ds, dst, vols, config, use_exit=False)
            results_fine_entry.append((pnl, trd, wins, dd, fb, config))

        results_fine_entry.sort(key=self._rank_key, reverse=True)
        best_no_exit_cfg = results_fine_entry[0][5]
        print(f"Stage 2 complete in {time.time() - start:.1f}s. Best: {best_no_exit_cfg}")

        print("\n>>> PHASE 1 RESULT (TRAIN SET — No Exit) <<<")
        self._run_and_print_final("Train / No Exit", best_no_exit_cfg, train_arrays, use_exit=False)

        print("\n>>> PHASE 1 RESULT (TEST SET — No Exit) <<<")
        self._run_and_print_final("Test / No Exit", best_no_exit_cfg, test_arrays, use_exit=False)

        # ===================================================================
        # PHASE 2: WITH-EXIT optimization (Stages 3-4)
        # ===================================================================
        print("\n" + "=" * 80)
        print("PHASE 2: WITH-EXIT OPTIMIZATION (Panic Exit Enabled)")
        print("=" * 80)

        print("\n=== Stage 3: Coarse Exit Search (0.05 step) ===")
        exit_coarse_range = [round(x, 2) for x in np.arange(0.50, 1.01, 0.05)]
        exit_coarse_combos = list(itertools.product(exit_coarse_range, exit_coarse_range, exit_coarse_range))

        results_coarse_exit: list[tuple] = []
        start = time.time()
        for e1, e2, e3 in exit_coarse_combos:
            config = {**best_no_exit_cfg, "ex_short": e1, "ex_mid": e2, "ex_struct": e3}
            pnl, trd, wins, dd, fb = self.simulate(p, tnr, tar, tdh, ds, dst, vols, config, use_exit=True)
            results_coarse_exit.append((pnl, trd, wins, dd, fb, config))

        results_coarse_exit.sort(key=self._rank_key, reverse=True)
        best_coarse_exit = results_coarse_exit[0][5]
        print(
            f"Stage 3 complete in {time.time() - start:.1f}s. Coarse exit: "
            f"ex_short={best_coarse_exit['ex_short']}, ex_mid={best_coarse_exit['ex_mid']}, "
            f"ex_struct={best_coarse_exit['ex_struct']}"
        )

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
            pnl, trd, wins, dd, fb = self.simulate(p, tnr, tar, tdh, ds, dst, vols, config, use_exit=True)
            results_fine_exit.append((pnl, trd, wins, dd, fb, config))

        results_fine_exit.sort(key=self._rank_key, reverse=True)
        best_exit_cfg = results_fine_exit[0][5]
        print(f"Stage 4 complete in {time.time() - start:.1f}s.")

        print("\n>>> PHASE 2 RESULT (TRAIN SET — With Exit) <<<")
        self._run_and_print_final("Train / With Exit", best_exit_cfg, train_arrays, use_exit=True)

        print("\n>>> PHASE 2 RESULT (TEST SET — With Exit) <<<")
        self._run_and_print_final("Test / With Exit", best_exit_cfg, test_arrays, use_exit=True)

        # ===================================================================
        # FINAL REPORT
        # ===================================================================
        print("\n" + "=" * 80)
        print(f"ULTIMATE SWEET SPOT REPORT  (v3.3 — last {MAX_MONTHS} months, synthetic 1s resolution)")
        print("=" * 80)

        print("\nOPTION 1: NO EXIT (Trend Reversal Only)")
        pnl1, trd1, *_ = self._run_and_print_final(
            "Full Dataset / No Exit", best_no_exit_cfg, all_arrays, use_exit=False,
        )

        print("\nOPTION 2: WITH EXIT (Panic Exit Enabled)")
        pnl2, trd2, *_ = self._run_and_print_final(
            "Full Dataset / With Exit", best_exit_cfg, all_arrays, use_exit=True,
        )

        ppt1 = pnl1 / max(1, trd1)
        ppt2 = pnl2 / max(1, trd2)
        if ppt1 >= ppt2:
            winner, winner_cfg, winner_exit = "NO EXIT", best_no_exit_cfg, False
            print("\nCONCLUSION: 'NO EXIT' is superior (higher profit/trade).")
        else:
            winner, winner_cfg, winner_exit = "WITH EXIT", best_exit_cfg, True
            print("\nCONCLUSION: 'WITH EXIT' is superior (higher profit/trade).")
        print(f"Winner: {winner}")
        print("=" * 80)

        self._export_config(winner_cfg, winner_exit)

    # -----------------------------------------------------------------------
    # Export config to JSON
    # -----------------------------------------------------------------------
    @staticmethod
    def _export_config(config: dict, use_exit: bool) -> None:
        output = {
            "consensus_short_term_threshold": config["c_short"],
            "consensus_mid_term_threshold":   config["c_mid"],
            "consensus_threshold":            config["c_struct"],
            "volatility_threshold":           config.get("vol_threshold", 0.0),
            "use_exit":                       use_exit,
        }
        if use_exit:
            output["exit_short_term_consensus_threshold"] = config.get("ex_short", 0.0)
            output["exit_mid_term_threshold"] = config.get("ex_mid", 0.0)
            output["exit_consensus_threshold"] = config.get("ex_struct", 0.0)

        out_path = Path("config") / "thresholds.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(output, f, indent=2)
        print(f"\nOptimized thresholds saved to {out_path}")


if __name__ == "__main__":
    opt = HighResPeakOptimizer("market_data/historical")
    opt.run()
