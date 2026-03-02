import os
import glob
import pandas as pd
import numpy as np
import time
from enum import IntFlag
import itertools

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
        print("[1/2] Vectorizing entire history...")
        csv_files = sorted(glob.glob(os.path.join(self.data_dir, "BTCUSDT-15m-*.csv")))
        df_list = [pd.read_csv(f, header=0, usecols=[0, 4], names=['timestamp', 'price']) for f in csv_files]
        df = pd.concat(df_list).sort_values('timestamp').reset_index(drop=True)
        
        prices = df['price'].values
        sma60 = df['price'].rolling(window=60).mean().values
        sma300 = df['price'].rolling(window=300).mean().values
        ema300 = df['price'].ewm(span=300, adjust=False).mean().values
        
        n = len(prices)
        sig_scores = np.zeros(n)
        sig_scores[sma60 > ema300] += 5
        sig_scores[sma60 < ema300] -= 5
        sig_scores[prices > sma300] += 3
        sig_scores[prices < sma300] -= 3
        
        def rolling_consensus(arr, window):
            return pd.Series(arr).rolling(window=window).mean().values / 8.0

        df['c_short'] = rolling_consensus(sig_scores, 24)
        df['c_mid'] = rolling_consensus(sig_scores, 60)
        df['c_struct'] = rolling_consensus(sig_scores, 120)
        df['density'] = pd.Series(sig_scores != 0).rolling(window=120).sum().values
        
        return df.dropna()

    def simulate(self, prices, c_short, c_mid, c_struct, densities, config):
        balance = 10000.0
        trade_weight = 0.15
        leverage = 10
        taker_fee = 0.0005
        
        current_side = 0 
        entry_price = 0
        trades = 0

        for i in range(len(prices)):
            if densities[i] < config['min_density']: 
                continue
            
            is_strong_buy = c_short[i] >= config['c_short'] and c_mid[i] >= config['c_mid'] and c_struct[i] >= config['c_struct']
            is_strong_sell = c_short[i] <= -config['c_short'] and c_mid[i] <= -config['c_mid'] and c_struct[i] <= -config['c_struct']
            
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
                if is_strong_sell:
                    pnl = (balance * trade_weight) * ((prices[i] - entry_price) / entry_price) * leverage
                    balance += pnl - (balance * trade_weight * leverage * 2 * taker_fee)
                    current_side = -1
                    entry_price = prices[i]
                    trades += 1

            elif current_side == -1:
                if is_strong_buy:
                    pnl = (balance * trade_weight) * ((entry_price - prices[i]) / entry_price) * leverage
                    balance += pnl - (balance * trade_weight * leverage * 2 * taker_fee)
                    current_side = 1
                    entry_price = prices[i]
                    trades += 1

        return balance - 10000.0, trades

    def run(self):
        df = self.load_and_signals()
        prices, cs, cm, cst, den = df['price'].values, df['c_short'].values, df['c_mid'].values, df['c_struct'].values, df['density'].values
        
        c_shorts = [0.9, 0.95, 1.0]
        c_mids = [0.65, 0.7, 0.75, 0.8]
        c_structs = [0.6, 0.65, 0.7, 0.75]
        min_densities = [10, 20, 30, 40]
        
        combos = list(itertools.product(c_shorts, c_mids, c_structs, min_densities))
        print(f"[2/2] High-Res Grid Search: {len(combos)} combinations...")
        
        results = []
        start = time.time()
        for cs_val, cm_val, cst_val, md in combos:
            config = {'c_short': cs_val, 'c_mid': cm_val, 'c_struct': cst_val, 'min_density': md}
            pnl, trd = self.simulate(prices, cs, cm, cst, den, config)
            results.append((pnl, trd, config))
            
        results.sort(key=lambda x: x[0], reverse=True)
        print(f"\nOptimization Complete in {time.time() - start:.2f}s")
        print("\nTOP 3 ABSOLUTE BEST COMBINATIONS:")
        for pnl, trd, cfg in results[:3]:
            pnl_pct = (pnl / 10000.0) * 100
            print(f"PnL: ${pnl:+.2f} ({pnl_pct:+.2f}%) | Trades: {trd} | Config: {cfg}")

if __name__ == "__main__":
    opt = HighResPeakOptimizer("data/historical")
    opt.run()
