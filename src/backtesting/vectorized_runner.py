import glob
import itertools
import os
import time
from enum import IntFlag

import numpy as np
import pandas as pd


class TradeSignal(IntFlag):
    SHORT_TERM_BUY = 1 << 0
    LONG_TERM_BUY = 1 << 1
    SHORT_TERM_SELL = 1 << 2
    LONG_TERM_SELL = 1 << 3
    HOLD = 1 << 4


class HighResPeakOptimizer:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir

    def load_and_signals(self):
        print("[1/2] Vectorizing entire history with OHLC expansion (x4 data points)...")
        csv_files = sorted(glob.glob(os.path.join(self.data_dir, "BTCUSDT-15m-*.csv")))

        # Read OHLC columns
        df_list = [pd.read_csv(f, header=0, usecols=[0, 1, 2, 3, 4], names=['timestamp', 'open', 'high', 'low', 'close']) for f in csv_files]
        df = pd.concat(df_list).sort_values('timestamp').reset_index(drop=True)

        # Determine sequence based on candle direction
        bullish = df['close'] >= df['open']

        tick1 = df['open'].values
        tick2 = np.where(bullish, df['low'].values, df['high'].values)
        tick3 = np.where(bullish, df['high'].values, df['low'].values)
        tick4 = df['close'].values

        # Interleave the ticks
        prices_matrix = np.empty((len(df), 4))
        prices_matrix[:, 0] = tick1
        prices_matrix[:, 1] = tick2
        prices_matrix[:, 2] = tick3
        prices_matrix[:, 3] = tick4

        flat_prices = prices_matrix.flatten()

        # Create the expanded dataframe
        expanded_df = pd.DataFrame({'price': flat_prices})
        expanded_df['price'] = expanded_df['price'] / 1_000

        prices = expanded_df['price'].values
        sma60 = expanded_df['price'].rolling(window=60).mean().values
        sma300 = expanded_df['price'].rolling(window=300).mean().values
        ema300 = expanded_df['price'].ewm(span=300, adjust=False).mean().values

        n = len(prices)
        sig_scores = np.zeros(n)
        sig_scores[sma60 > ema300] += 5
        sig_scores[sma60 < ema300] -= 5
        sig_scores[prices > sma300] += 3
        sig_scores[prices < sma300] -= 3

        def rolling_consensus(arr, window):
            return pd.Series(arr).rolling(window=window).mean().values / 8.0

        expanded_df['c_short'] = rolling_consensus(sig_scores, 120)  # 2 minutes
        expanded_df['c_mid'] = rolling_consensus(sig_scores, 300)    # 5 minutes
        expanded_df['c_struct'] = rolling_consensus(sig_scores, 600)  # 10 minutes
        expanded_df['density'] = pd.Series(sig_scores != 0).rolling(window=600).sum().values  # 10 minutes

        return expanded_df.dropna()

    def simulate(self, prices, c_short, c_mid, c_struct, densities, config, use_exit=False):
        balance = 10000.0
        trade_weight = 0.15
        leverage = 10
        taker_fee = 0.001

        current_side = 0
        entry_price = 0
        trades = 0

        for i in range(len(prices)):
            # Entry/Reverse Conditions
            is_strong_buy = c_short[i] >= config['c_short'] and c_mid[i] >= config['c_mid'] and c_struct[i] >= config['c_struct']
            is_strong_sell = c_short[i] <= -config['c_short'] and c_mid[i] <= -config['c_mid'] and c_struct[i] <= -config['c_struct']

            # Exit Conditions (Flipped consensus)
            is_exit_buy = False
            is_exit_sell = False
            if use_exit:
                is_exit_buy = c_short[i] < -config['ex_short'] and c_mid[i] < -config['ex_mid'] and c_struct[i] < -config['ex_struct']
                is_exit_sell = c_short[i] > config['ex_short'] and c_mid[i] > config['ex_mid'] and c_struct[i] > config['ex_struct']

            if current_side == 0:
                if is_strong_buy:
                    current_side = 1
                    entry_price = prices[i]
                    trades += 1
                elif is_strong_sell:
                    current_side = -1
                    entry_price = prices[i]
                    trades += 1

            elif current_side == 1:
                if is_strong_sell:  # REVERSE
                    pnl = (balance * trade_weight) * ((prices[i] - entry_price) / entry_price) * leverage
                    balance += pnl - (balance * trade_weight * leverage * 2 * taker_fee)
                    current_side = -1
                    entry_price = prices[i]
                    trades += 1
                elif use_exit and is_exit_buy:  # PANIC EXIT
                    pnl = (balance * trade_weight) * ((prices[i] - entry_price) / entry_price) * leverage
                    balance += pnl - (balance * trade_weight * leverage * taker_fee)
                    current_side = 0
                    trades += 1

            elif current_side == -1:
                if is_strong_buy:  # REVERSE
                    pnl = (balance * trade_weight) * ((entry_price - prices[i]) / entry_price) * leverage
                    balance += pnl - (balance * trade_weight * leverage * 2 * taker_fee)
                    current_side = 1
                    entry_price = prices[i]
                    trades += 1
                elif use_exit and is_exit_sell:  # PANIC EXIT
                    pnl = (balance * trade_weight) * ((entry_price - prices[i]) / entry_price) * leverage
                    balance += pnl - (balance * trade_weight * leverage * taker_fee)
                    current_side = 0
                    trades += 1

        return balance - 10000.0, trades

    def run(self):
        df = self.load_and_signals()
        prices, cs, cm, cst, den = df['price'].values, df['c_short'].values, df['c_mid'].values, df['c_struct'].values, df['density'].values

        print("\n=== STAGE 1: Coarse Entry Search (0.05 step, No Exit) ===")
        coarse_range = [round(x, 2) for x in np.arange(0.50, 1.01, 0.05)]
        coarse_combos = list(itertools.product(coarse_range, coarse_range, coarse_range))

        results_coarse_entry = []
        start = time.time()
        for c1, c2, c3 in coarse_combos:
            config = {'c_short': c1, 'c_mid': c2, 'c_struct': c3}
            pnl, trd = self.simulate(prices, cs, cm, cst, den, config, use_exit=False)
            results_coarse_entry.append((pnl, trd, config))

        results_coarse_entry.sort(key=lambda x: x[0] / max(1, x[1]), reverse=True)
        best_coarse_entry = results_coarse_entry[0][2]
        print(f"Stage 1 Complete in {time.time() - start:.2f}s. Coarse Entry: {best_coarse_entry}")

        print("\n=== STAGE 2: Fine Entry Search (0.01 step, No Exit) ===")

        def get_fine_range(center):
            start = max(0.50, center - 0.05)
            end = min(1.00, center + 0.05)
            return [round(x, 2) for x in np.arange(start, end + 0.005, 0.01)]

        fine_entry_combos = list(itertools.product(
            get_fine_range(best_coarse_entry['c_short']),
            get_fine_range(best_coarse_entry['c_mid']),
            get_fine_range(best_coarse_entry['c_struct'])
        ))

        results_fine_entry = []
        start = time.time()
        for c1, c2, c3 in fine_entry_combos:
            config = {'c_short': c1, 'c_mid': c2, 'c_struct': c3}
            pnl, trd = self.simulate(prices, cs, cm, cst, den, config, use_exit=False)
            results_fine_entry.append((pnl, trd, config))

        results_fine_entry.sort(key=lambda x: x[0] / max(1, x[1]), reverse=True)
        best_fine_entry = results_fine_entry[0][2]
        best_fine_entry_pnl, best_fine_entry_trd = results_fine_entry[0][0], results_fine_entry[0][1]
        print(f"Stage 2 Complete in {time.time() - start:.2f}s.")

        print("\n=== STAGE 3: Coarse Exit Search (0.05 step, With Exit) ===")
        results_coarse_exit = []
        start = time.time()
        for e1, e2, e3 in coarse_combos:
            config = {**best_fine_entry, 'ex_short': e1, 'ex_mid': e2, 'ex_struct': e3}
            pnl, trd = self.simulate(prices, cs, cm, cst, den, config, use_exit=True)
            results_coarse_exit.append((pnl, trd, config))

        results_coarse_exit.sort(key=lambda x: x[0] / max(1, x[1]), reverse=True)
        best_coarse_exit = results_coarse_exit[0][2]
        print(
            f"Stage 3 Complete in {time.time() - start:.2f}s. Coarse Exit: ex_short="
            f"{best_coarse_exit['ex_short']}, ex_mid={best_coarse_exit['ex_mid']}, "
            f"ex_struct={best_coarse_exit['ex_struct']}"
        )

        print("\n=== STAGE 4: Fine Exit Search (0.01 step, With Exit) ===")
        fine_exit_combos = list(itertools.product(
            get_fine_range(best_coarse_exit['ex_short']),
            get_fine_range(best_coarse_exit['ex_mid']),
            get_fine_range(best_coarse_exit['ex_struct'])
        ))

        results_fine_exit = []
        start = time.time()
        for e1, e2, e3 in fine_exit_combos:
            config = {**best_fine_entry, 'ex_short': e1, 'ex_mid': e2, 'ex_struct': e3}
            pnl, trd = self.simulate(prices, cs, cm, cst, den, config, use_exit=True)
            results_fine_exit.append((pnl, trd, config))

        results_fine_exit.sort(key=lambda x: x[0] / max(1, x[1]), reverse=True)
        best_fine_exit_config = results_fine_exit[0][2]
        best_fine_exit_pnl, best_fine_exit_trd = results_fine_exit[0][0], results_fine_exit[0][1]
        print(f"Stage 4 Complete in {time.time() - start:.2f}s.")

        # Final Output
        print("\n" + "="*80)
        print("ULTIMATE SWEET SPOT REPORT (0.01 Precision, Ranked by Profit/Trade)")
        print("="*80)

        print("\n🏆 OPTION 1: NO EXIT (Trend Reversal Only)")
        ppt1 = best_fine_entry_pnl / max(1, best_fine_entry_trd)
        print(f"PnL: ${best_fine_entry_pnl:+.2f} ({(best_fine_entry_pnl/10000.0)*100:+.2f}%) | Trades: {best_fine_entry_trd} | Profit/Trade: ${ppt1:.2f}")
        print(f"Entry Thresholds: Short: {best_fine_entry['c_short']:.2f}, Mid: {best_fine_entry['c_mid']:.2f}, Struct: {best_fine_entry['c_struct']:.2f}")

        print("\n🏆 OPTION 2: WITH EXIT (Panic Exit enabled)")
        ppt2 = best_fine_exit_pnl / max(1, best_fine_exit_trd)
        print(f"PnL: ${best_fine_exit_pnl:+.2f} ({(best_fine_exit_pnl/10000.0)*100:+.2f}%) | Trades: {best_fine_exit_trd} | Profit/Trade: ${ppt2:.2f}")
        print(f"Entry Thresholds: Short: {best_fine_exit_config['c_short']:.2f}, Mid: {best_fine_exit_config['c_mid']:.2f}, Struct: {best_fine_exit_config['c_struct']:.2f}")
        print(f"Exit Thresholds:  Short: {best_fine_exit_config['ex_short']:.2f}, Mid: {best_fine_exit_config['ex_mid']:.2f}, Struct: {best_fine_exit_config['ex_struct']:.2f}")

        if ppt1 >= ppt2:
            print("\nCONCLUSION: 'NO EXIT' is mathematically superior (Higher Profit per Trade).")
        else:
            print("\nCONCLUSION: 'WITH EXIT' is mathematically superior (Higher Profit per Trade).")
        print("="*80 + "\n")


if __name__ == "__main__":
    opt = HighResPeakOptimizer("data/historical")
    opt.run()
