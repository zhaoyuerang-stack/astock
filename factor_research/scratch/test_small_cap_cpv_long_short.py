"""Research Script: Long-Short CPV Strategy in the Small-Cap Universe.

Tests the performance of a 5-quintile CPV strategy in the bottom 1000 stocks
to evaluate if the short leg of high-CPV small-caps generates extreme alpha.
"""
import os
import sys
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np
import pandas as pd

# Align to project root
PROJECT_ROOT = Path(__file__).resolve().parents[1]
os.chdir(PROJECT_ROOT)
sys.path.append(str(PROJECT_ROOT))

from core.engine import BacktestEngine, BacktestConfig, Signal, PricePanel, CostModel
from strategies.small_cap import load_price_panels

# Helper: Vectorized Correlation
def vectorized_rolling_corr(df1, df2, window=20):
    mean1 = df1.rolling(window).mean()
    mean2 = df2.rolling(window).mean()
    mean_prod = (df1 * df2).rolling(window).mean()
    cov = mean_prod - mean1 * mean2
    std1 = df1.rolling(window).std()
    std2 = df2.rolling(window).std()
    return cov / (std1 * std2 + 1e-8)

# Helper: Metrics
def get_metrics(ret):
    if len(ret) == 0:
        return {"annual": 0.0, "sharpe": 0.0, "maxdd": 0.0}
    nav = (1 + ret.fillna(0)).cumprod()
    ann = nav.iloc[-1] ** (252 / len(ret)) - 1
    sharpe = ret.mean() / ret.std() * np.sqrt(252) if ret.std() > 0 else 0.0
    maxdd = float((nav / nav.cummax() - 1).min())
    return {"annual": ann, "sharpe": sharpe, "maxdd": maxdd}

def main():
    print("=" * 85)
    print("  RESEARCH: 5-QUINTILE CPV STRATEGY IN THE SMALL-CAP UNIVERSE (BOTTOM 1000)  ")
    print("=" * 85)

    # 1. Load Data
    print("\n[1/3] Loading small-cap prices and amounts...", flush=True)
    close, volume, amount = load_price_panels("2010-01-01")
    
    # Exclude corrupted dates
    clean_dates = close.index[close.index < "2026-06-10"]
    close = close.reindex(clean_dates)
    amount = amount.reindex(clean_dates)
    
    prices = PricePanel(close=close, volume=amount*0, amount=amount, raw_close=close)

    # 2. Compute CPV and Universe
    print("\n[2/3] Computing CPV and defining bottom 1000 universe...", flush=True)
    cpv = vectorized_rolling_corr(close, amount, window=20)
    
    # Universe: Bottom 1000 stocks by liquidity (average amount)
    avg_amt = amount.rolling(20).mean()
    univ = avg_amt.rank(axis=1, ascending=True, pct=False) <= 1000
    
    cpv_filtered = cpv.where(univ)

    # 3. Simulate 5-Quintile Portfolios
    print("\n[3/3] Simulating 5-Quintile backtests...", flush=True)
    rebalance_days = 20
    rebal_dates = cpv.index[120::rebalance_days]
    costs = CostModel(buy_cost=0.00225, sell_cost=0.00275, financing_rate=0.0)
    config = BacktestConfig(start="2012-01-01", cost=costs, leverage=1.0)
    
    quintile_returns = {}
    
    for q in [1, 5]:
        weights = {}
        for i in range(len(rebal_dates)):
            dt_current = rebal_dates[i]
            pos = close.index.get_loc(dt_current)
            if pos + 1 >= len(close.index):
                continue
            effective_date = close.index[pos + 1]
            
            f = cpv_filtered.loc[dt_current].dropna()
            if len(f) < 100:
                continue
                
            if q == 1:
                # Lowest CPV (Stealth Bottoms)
                stocks = f.nsmallest(int(len(f) * 0.2)).index.tolist()
            else:
                # Highest CPV (Bubbles)
                stocks = f.nlargest(int(len(f) * 0.2)).index.tolist()
                
            if len(stocks) > 0:
                weights[effective_date] = pd.Series(1.0 / len(stocks), index=stocks)
                
        engine = BacktestEngine(prices=prices, config=config)
        res = engine.run(Signal(weights=weights, timing=None))
        quintile_returns[f"Q{q}"] = res.returns

    # Reference small-cap benchmark (equal-weighted bottom 1000)
    daily_ret = close.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    bench_returns = pd.Series(0.0, index=daily_ret.index)
    univ_shifted = univ.shift(1)
    for dt in daily_ret.index:
        active = univ_shifted.loc[dt] if dt in univ_shifted.index else pd.Series(False, index=univ.columns)
        active = active.fillna(False).astype(bool)
        active_codes = active[active].index
        if len(active_codes) > 0:
            bench_returns.loc[dt] = daily_ret.loc[dt, active_codes].mean()

    # Compare Results
    for label, start_yr in [("Full Period (2012-2026)", 2012), ("OOS Period (2023-2026)", 2023)]:
        print("\n" + "=" * 95)
        print(f"  SMALL-CAP LONG-SHORT CPV MATRIX: {label}")
        print("=" * 95)
        print(f"{'Portfolio / Quintile':<45} | {'Annual Return':<13} | {'Sharpe':<7} | {'Max Drawdown':<12}")
        print("-" * 95)
        
        # Benchmark
        b_slice = bench_returns[bench_returns.index.year >= start_yr]
        m_bench = get_metrics(b_slice)
        print(f"Bottom 1000 Benchmark {label:<22} | {m_bench['annual']:>13.2%} | {m_bench['sharpe']:>7.2f} | {m_bench['maxdd']:>12.2%}")
        print("-" * 95)
        
        # Q1 and Q5
        q1_s = quintile_returns["Q1"][quintile_returns["Q1"].index.year >= start_yr]
        q5_s = quintile_returns["Q5"][quintile_returns["Q5"].index.year >= start_yr]
        
        m_q1 = get_metrics(q1_s)
        print(f"Quintile 1 (Lowest CPV / Stealth Bottoms)     | {m_q1['annual']:>13.2%} | {m_q1['sharpe']:>7.2f} | {m_q1['maxdd']:>12.2%}")
        
        m_q5 = get_metrics(q5_s)
        print(f"Quintile 5 (Highest CPV / Speculative Bubbles) | {m_q5['annual']:>13.2%} | {m_q5['sharpe']:>7.2f} | {m_q5['maxdd']:>12.2%}")
        
        # Spread (Long Q1, Short Q5)
        r_spread = q1_s - q5_s
        m_spread = get_metrics(r_spread)
        print(f"Long-Short Spread (Q1 - Q5)                   | {m_spread['annual']:>13.2%} | {m_spread['sharpe']:>7.2f} | {m_spread['maxdd']:>12.2%}")
        print("=" * 95)

if __name__ == "__main__":
    main()
