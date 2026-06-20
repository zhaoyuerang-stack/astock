"""Research Script: Estimating Capital Capacity of CPV Strategies.

Calculates the average daily trading amount (ADDV) of the selected holdings
for both baseline and upgraded CPV strategies to estimate and compare their
capital capacities.
"""
import os
import sys
import warnings
warnings.filterwarnings("ignore")
from pathlib import Path
import numpy as np
import pandas as pd

# Align to project root
PROJECT_ROOT = Path("/Users/kiki/astcok/factor_research")
os.chdir(PROJECT_ROOT)
sys.path.append(str(PROJECT_ROOT))

from factors.large_cap import load_clean_panels_with_growth, build_universe

def vectorized_rolling_corr(df1, df2, window=20):
    mean1 = df1.rolling(window).mean()
    mean2 = df2.rolling(window).mean()
    mean_prod = (df1 * df2).rolling(window).mean()
    cov = mean_prod - mean1 * mean2
    std1 = df1.rolling(window).std()
    std2 = df2.rolling(window).std()
    return cov / (std1 * std2 + 1e-8)

def main():
    print("=" * 80)
    print("  QUANTITATIVE CAPACITY AUDIT: CPV STRATEGY CAPACITY ANALYSIS  ")
    print("=" * 80)

    # 1. Load Data
    print("\n[1/3] Loading data...", flush=True)
    panels = load_clean_panels_with_growth()
    close = panels["close"]
    amount = panels["amount"]
    raw_close = panels["raw_close"]
    
    clean_dates = close.index[close.index < "2026-06-10"]
    close = close.reindex(clean_dates)
    amount = amount.reindex(clean_dates)
    raw_close = raw_close.reindex(clean_dates)
    
    # 2. Compute Universe and Factors
    print("\n[2/3] Computing factors...", flush=True)
    cap = amount.rolling(20).mean() * raw_close
    univ = cap.rank(axis=1, ascending=False, pct=False) <= 200
    
    cpv = vectorized_rolling_corr(close, amount, window=20)
    
    # Baseline: Raw CPV
    f_raw = cpv.where(univ)
    
    # Upgraded: Rank Product
    cpv_raw_r = cpv.rank(axis=1, pct=True, na_option="bottom")
    m_liq = 1.0 / (amount.rolling(20).mean() + 1.0)
    m_liq_r = m_liq.rank(axis=1, pct=True, na_option="bottom")
    f_rank_prod = (cpv_raw_r * m_liq_r).rank(axis=1, pct=True, na_option="bottom").where(univ)

    # 3. Calculate Capacity
    print("\n[3/3] Auditing capital capacity of selected holdings...", flush=True)
    rebalance_days = 20
    rebal_dates = cpv.index[120::rebalance_days]
    
    # ADDV of Top 200 universe for comparison
    avg_addv_univ = amount.rolling(20).mean().where(univ)
    
    capacity_records = []
    
    for dt in rebal_dates:
        # Get active holdings for Q1 (Lowest factor values)
        # Raw CPV
        f_raw_dt = f_raw.loc[dt].dropna()
        if len(f_raw_dt) >= 50:
            q1_raw = f_raw_dt.nsmallest(25).index
            # Get 20-day average daily trading amount (in Yuan) of holdings
            addv_raw = amount.loc[dt, q1_raw].mean()
        else:
            addv_raw = np.nan
            
        # Upgraded Rank Product
        f_upg_dt = f_rank_prod.loc[dt].dropna()
        if len(f_upg_dt) >= 50:
            q1_upg = f_upg_dt.nsmallest(25).index
            addv_upg = amount.loc[dt, q1_upg].mean()
        else:
            addv_upg = np.nan
            
        # Benchmark Top 200 ADDV
        addv_bench = avg_addv_univ.loc[dt].mean()
        
        capacity_records.append({
            "date": dt,
            "addv_raw": addv_raw,
            "addv_upg": addv_upg,
            "addv_bench": addv_bench
        })
        
    df_cap = pd.DataFrame(capacity_records).dropna().set_index("date")
    
    # Compute median ADDV over full period and OOS
    for label, start_yr in [("Full Period (2012-2026)", 2012), ("OOS Period (2023-2026)", 2023)]:
        df_slice = df_cap[df_cap.index.year >= start_yr]
        
        med_raw = df_slice["addv_raw"].median() / 1e8 # In hundred million Yuan
        med_upg = df_slice["addv_upg"].median() / 1e8
        med_bench = df_slice["addv_bench"].median() / 1e8
        
        # Capacity estimation:
        # Assuming we rebalance 25 stocks every 20 days.
        # Max trade volume in a single day is 1% of ADDV to keep slippage low.
        # For a portfolio size V, rebalancing means shifting 100% of weights.
        # If we rebalance 25 stocks, typical turnover is around 70%.
        # Total traded amount = V * 0.70.
        # We execute this over 1 day. Trade amount per stock = (V * 0.70) / 25.
        # This must be <= 1% of ADDV: (V * 0.70) / 25 <= 0.01 * ADDV
        # V <= 0.01 * ADDV * 25 / 0.70 = 0.357 * ADDV
        # Let's use 0.35 * ADDV as a conservative capacity estimate!
        cap_raw = med_raw * 0.35 * 100 # In million Yuan
        cap_upg = med_upg * 0.35 * 100
        cap_bench = med_bench * 0.35 * 100
        
        print("\n" + "=" * 95)
        print(f"  CAPACITY METRICS SUMMARY: {label}")
        print("=" * 95)
        print(f"{'Strategy Variant':<45} | {'Median ADDV (亿元)':<20} | {'Estimated Cap (百万元)':<22}")
        print("-" * 95)
        print(f"Top 200 Benchmark Index                       | {med_bench:>18.2f} | {cap_bench:>20.1f}")
        print(f"Raw CPV (Baseline Q1)                         | {med_raw:>18.2f} | {cap_raw:>20.1f}")
        print(f"Upgraded CPV (Rank Product Q1)                | {med_upg:>18.2f} | {cap_upg:>20.1f}")
        
        # Calculate percentage change in capacity
        cap_chg = (cap_upg / cap_raw - 1.0)
        print(f"--> Upgraded Strategy Capacity Increase: {cap_chg:+.2%}")
        print("=" * 95)

if __name__ == "__main__":
    main()
